"""
Pruebas automatizadas de caja blanca y caja negra — MVP Fase 1
Fundación Hermandad de Dolores (compatibles con pytest y unittest).
"""

import unittest
from fastapi.testclient import TestClient

from app.domain.estados import EstadoConfirmacion, ErrorTransicionEstado, aplicar_regla_confirmacion, obtener_estado_cita
from app.domain.rut import enmascarar_nombre, formatear_rut, validar_rut
from app.main import crear_app
from app.repositories.repositorio_memoria import RepositorioCitaMemoria


class TestDominioYReglas(unittest.TestCase):
    def test_rut_modulo_11_valido_e_invalido(self):
        self.assertTrue(validar_rut("14.567.890-0"))
        self.assertTrue(validar_rut("163456788"))
        self.assertEqual(formatear_rut("145678900"), "14.567.890-0")
        self.assertFalse(validar_rut("14.567.890-9"))
        self.assertFalse(validar_rut("123"))

    def test_enmascaramiento_privacidad_p10(self):
        self.assertEqual(enmascarar_nombre("María Elena Pérez Demo"), "María E*** P*** D***")

    def test_regla_rf09_el_silencio_no_cancela(self):
        estado_cita, estado_conf = aplicar_regla_confirmacion("RESERVADA", EstadoConfirmacion.SIN_RESPUESTA)
        self.assertEqual(estado_cita, "RESERVADA")
        self.assertEqual(estado_conf, "SIN_RESPUESTA")

    def test_patron_state_transiciones_invalidas(self):
        est_asistida = obtener_estado_cita("ASISTIDA")
        with self.assertRaises(ErrorTransicionEstado):
            est_asistida.cancelar()
        est_cancelada = obtener_estado_cita("CANCELADA")
        with self.assertRaises(ErrorTransicionEstado):
            est_cancelada.registrar_asistencia()


class TestApiEndToEnd(unittest.TestCase):
    def setUp(self):
        self.repo = RepositorioCitaMemoria()
        self.app = crear_app(repo=self.repo)
        self.client = TestClient(self.app)

    def test_salud_y_frontend_html(self):
        r_html = self.client.get("/")
        self.assertEqual(r_html.status_code, 200)
        self.assertIn("Fundación Hermandad de Dolores", r_html.text)

        r_api = self.client.get("/api/salud")
        self.assertEqual(r_api.status_code, 200)
        self.assertEqual(r_api.json()["estado"], "ok")

    def test_prevencion_doble_reserva_rnf04_y_comprobante_sin_codigo_rf28(self):
        # Primera reserva en bloque disponible id=2 -> 201 Created
        payload = {"paciente_rut": "14.567.890-0", "bloque_id": 2, "canal_registro": "ASISTIDO_PRESENCIAL"}
        r1 = self.client.post("/api/citas", json=payload)
        self.assertEqual(r1.status_code, 201)
        body = r1.json()
        self.assertIn("comprobante_sin_codigo", body)
        self.assertNotIn("codigo_reserva", body["comprobante_sin_codigo"])

        # Segunda reserva en el mismo bloque id=2 -> 409 Conflict (RNF04)
        r2 = self.client.post("/api/citas", json={"paciente_rut": "19.876.543-0", "bloque_id": 2})
        self.assertEqual(r2.status_code, 409)

    def test_confirmacion_sin_respuesta_mantiene_cita_y_cancelacion_libera_cupo(self):
        # Cita id=1 está RESERVADA -> marcar SIN_RESPUESTA la mantiene RESERVADA (RF09)
        r_sr = self.client.patch("/api/citas/1/confirmacion", json={"estado_confirmacion": "SIN_RESPUESTA"})
        self.assertEqual(r_sr.status_code, 200)
        self.assertEqual(r_sr.json()["estado_cita"], "RESERVADA")
        self.assertEqual(r_sr.json()["estado_confirmacion"], "SIN_RESPUESTA")

        # Cancelar explícitamente -> estado CANCELADA y libera bloque id=1 (RF11)
        r_can = self.client.post("/api/citas/1/cancelar", json={"origen_cancelacion": "WHATSAPP_PACIENTE", "motivo": "Prueba"})
        self.assertEqual(r_can.status_code, 200)
        self.assertEqual(r_can.json()["estado_cita"], "CANCELADA")

        bloques = self.client.get("/api/bloques?solo_disponibles=true").json()
        self.assertTrue(any(b["id"] == 1 for b in bloques))

    def test_asistencia_rf14_dispara_encuesta_rf30_y_consulta_rut_p10(self):
        r_asist = self.client.post("/api/citas/1/asistencia", json={"asistio": True})
        self.assertEqual(r_asist.status_code, 200)
        self.assertEqual(r_asist.json()["cita"]["estado_cita"], "ASISTIDA")
        self.assertIsNotNone(r_asist.json()["invitacion_encuesta_post_atencion"])

        r_pub = self.client.get("/api/publico/consulta-rut?rut=14.567.890-0")
        self.assertEqual(r_pub.status_code, 200)
        self.assertTrue(r_pub.json()["encontrado"])
        self.assertIn("***", r_pub.json()["paciente_enmascarado"])

    def test_reportes_y_exportacion_csv_rf23(self):
        r_rep = self.client.get("/api/reportes")
        self.assertEqual(r_rep.status_code, 200)
        self.assertEqual(len(r_rep.json()["indicadores_por_sede"]), 7)

        r_csv = self.client.get("/api/reportes/exportar-csv")
        self.assertEqual(r_csv.status_code, 200)
        self.assertIn("San Isidro (Casa Central)", r_csv.text)


if __name__ == "__main__":
    unittest.main()
