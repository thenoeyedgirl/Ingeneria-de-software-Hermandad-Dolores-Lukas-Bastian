"""Pruebas de filtros y gráficos — Dataset de reportería y CSV (RF19–RF23, RNF03). Repositorio en memoria."""

import json
import unittest
from datetime import date, timedelta

from fastapi.testclient import TestClient

from app.domain.reportes import CAMPOS_PROHIBIDOS, celda_csv_segura, tramo_etario
from app.main import crear_app
from app.repositories.repositorio_memoria import RepositorioCitaMemoria


class TestDatasetReportes(unittest.TestCase):
    def setUp(self):
        self.repo = RepositorioCitaMemoria()
        self.app = crear_app(repo=self.repo)
        self.client = TestClient(self.app)

    def _todas_las_claves(self, obj, acumulado=None):
        acumulado = set() if acumulado is None else acumulado
        if isinstance(obj, dict):
            for k, v in obj.items():
                acumulado.add(k)
                self._todas_las_claves(v, acumulado)
        elif isinstance(obj, list):
            for v in obj:
                self._todas_las_claves(v, acumulado)
        return acumulado

    def test_el_dataset_no_contiene_datos_personales_rnf03(self):
        r = self.client.get("/api/reportes/dataset")
        self.assertEqual(r.status_code, 200)
        cuerpo = r.json()
        claves = self._todas_las_claves(cuerpo)
        for prohibida in ("rut", "paciente_rut", "paciente_nombre", "telefono", "correo", *CAMPOS_PROHIBIDOS):
            self.assertNotIn(prohibida, claves)
        texto = json.dumps(cuerpo, ensure_ascii=False)
        for dato in ("14.567.890-0", "María Elena Pérez", "+56 9 5000", "maria.demo@ejemplo.cl"):
            self.assertNotIn(dato, texto)
        self.assertEqual(set(cuerpo), {"filtros_aplicados", "citas", "bloques", "encuestas", "catalogos"})
        self.assertGreaterEqual(len(cuerpo["catalogos"]["policlinicos"]), 7)  # 6 sedes + Telemedicina (RF35)

    def test_filtrar_por_policlinico_devuelve_solo_esa_sede(self):
        todas = self.client.get("/api/reportes/dataset").json()
        self.assertGreater(len({c["policlinico_id"] for c in todas["citas"]}), 0)
        r = self.client.get("/api/reportes/dataset?policlinico_id=1").json()
        self.assertTrue(r["citas"])
        self.assertTrue(all(c["policlinico_id"] == 1 for c in r["citas"]))
        self.assertTrue(all(b["policlinico_id"] == 1 for b in r["bloques"]))
        self.assertEqual(r["filtros_aplicados"]["policlinico_id"], 1)
        vacio = self.client.get("/api/reportes/dataset?policlinico_id=7").json()
        self.assertEqual(vacio["citas"], [])

    def test_filtros_combinables_estado_canal_y_fechas(self):
        ayer = (date.today() - timedelta(days=1)).isoformat()
        r = self.client.get(f"/api/reportes/dataset?estado_cita=ASISTIDA&desde={ayer}&hasta={ayer}").json()
        self.assertEqual([c["estado_cita"] for c in r["citas"]], ["ASISTIDA"])
        self.assertEqual(r["citas"][0]["fecha_cita"], ayer)
        r2 = self.client.get("/api/reportes/dataset?canal_registro=SOLICITUD_WEB").json()
        self.assertEqual(r2["citas"], [])
        r3 = self.client.get("/api/reportes/dataset?modalidad=TELEMEDICINA").json()
        self.assertTrue(all(c["modalidad"] == "TELEMEDICINA" for c in r3["citas"]))

    def test_tipo_fecha_solicitud_filtra_por_fecha_de_creacion(self):
        manana = (date.today() + timedelta(days=30)).isoformat()
        r = self.client.get(f"/api/reportes/dataset?tipo_fecha=solicitud&desde={manana}").json()
        self.assertEqual(r["citas"], [])
        hoy = date.today().isoformat()
        r2 = self.client.get(f"/api/reportes/dataset?tipo_fecha=solicitud&desde={hoy}&hasta={hoy}").json()
        self.assertEqual(len(r2["citas"]), 2)  # las 2 citas del semillero se crearon hoy

    def test_desde_mayor_que_hasta_devuelve_400(self):
        for url in ("/api/reportes/dataset?desde=2026-12-01&hasta=2026-11-01",
                    "/api/reportes/dataset.csv?desde=2026-12-01&hasta=2026-11-01"):
            self.assertEqual(self.client.get(url).status_code, 400)

    def test_parametros_invalidos_devuelven_400(self):
        for q in ("desde=hoy", "hasta=2026-13-45", "tipo_fecha=otro", "estado_cita=BORRADA", "canal_registro=FAX", "modalidad=ONLINE"):
            self.assertEqual(self.client.get(f"/api/reportes/dataset?{q}").status_code, 400, q)

    def test_csv_con_bom_encabezado_en_espanol_y_auditoria(self):
        r = self.client.get("/api/reportes/dataset.csv?policlinico_id=1")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.content.startswith(b"\xef\xbb\xbf"))
        texto = r.content.decode("utf-8-sig")
        primera = texto.splitlines()[0]
        for col in ("Fecha de la cita", "Estado de la cita", "Policlínico", "Profesional", "Tramo etario"):
            self.assertIn(col, primera)
        self.assertIn("San Isidro (Casa Central)", texto)
        for dato in ("14.567.890-0", "María Elena", "maria.demo"):
            self.assertNotIn(dato, texto)
        self.assertIn("attachment", r.headers["content-disposition"])
        reg = [a for a in self.client.get("/api/auditoria").json() if a["operacion"] == "REPORTE_EXPORTAR"]
        self.assertEqual(len(reg), 1)
        self.assertEqual(reg[0]["usuario_nombre"], "Administración Central (Demo)")
        self.assertIn("policlinico_id=1", reg[0]["detalle"])
        # el frontend informa quién exporta
        self.client.get("/api/reportes/dataset.csv?usuario=Ana%20Admin&rol=ADMINISTRACION")
        reg2 = [a for a in self.client.get("/api/auditoria").json() if a["operacion"] == "REPORTE_EXPORTAR"]
        self.assertEqual(reg2[0]["usuario_nombre"], "Ana Admin")

    def test_csv_neutraliza_formulas(self):
        self.assertEqual(celda_csv_segura("=1+1"), "'=1+1")
        self.assertEqual(celda_csv_segura("Normal"), "Normal")
        self.assertEqual(celda_csv_segura(None), "")
        self.assertEqual(celda_csv_segura(5), 5)

    def test_tramos_etarios(self):
        hoy = date(2026, 11, 23)
        self.assertEqual(tramo_etario("2012-03-14", hoy), "0–17 años")
        self.assertEqual(tramo_etario("2000-01-01", hoy), "18–35 años")
        self.assertEqual(tramo_etario("1985-05-10", hoy), "36–59 años")
        self.assertEqual(tramo_etario("1950-01-01", hoy), "60+ años")
        self.assertEqual(tramo_etario(None, hoy), "Sin dato")

    def test_encuestas_en_dataset_con_su_sede(self):
        r = self.client.get("/api/reportes/dataset").json()
        self.assertEqual(r["encuestas"][0]["tipo"], "POST_ATENCION")
        self.assertEqual(r["encuestas"][0]["policlinico_id"], 1)


if __name__ == "__main__":
    unittest.main()
