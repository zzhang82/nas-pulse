import unittest
from nas_pulse.formatter import PulseReport, looks_temporary_container
from nas_pulse.constants import evaluate_cpu_temp

class TestFormatter(unittest.TestCase):
    def test_looks_temporary_container(self):
        self.assertTrue(looks_temporary_container("homepage-writer-1"))
        self.assertTrue(looks_temporary_container("uptime-kuma-swap-2026"))
        self.assertTrue(looks_temporary_container("cpa-widget-file"))
        self.assertFalse(looks_temporary_container("vaultwarden"))
        self.assertFalse(looks_temporary_container("jellyfin"))

    def test_evaluate_cpu_temp(self):
        rating, style = evaluate_cpu_temp(35)
        self.assertEqual(rating, "冰凉")
        rating, style = evaluate_cpu_temp(48)
        self.assertEqual(rating, "正常")
        rating, style = evaluate_cpu_temp(65)
        self.assertEqual(rating, "微热")
        rating, style = evaluate_cpu_temp(80)
        self.assertEqual(rating, "烫手")

    def test_pulse_report_generation(self):
        fake_vitals = {
            "cpu_util": {"user_load": 5, "system_load": 5},
            "mem_util": {"total_real": 20 * 1024 * 1024, "real_usage": 30, "cached": 10 * 1024 * 1024},
            "cpu_temp": 46,
            "vol_info": [{"total_size": 30 * (1024**4), "used_size": 10 * (1024**4)}],
            "hdd_info": [{"smart_status": "normal", "temp": 32}, {"smart_status": "normal", "temp": 33}],
            "sys_health": {"data": {"uptime": "240:00:00"}},
            "containers": [
                {"name": "vaultwarden", "status": "running"},
                {"name": "jellyfin", "status": "running"},
                {"name": "test-writer-helper", "status": "stopped"},
            ],
            "resources": [
                {"name": "vaultwarden", "cpu": 0.5, "memory": 50 * 1024 * 1024, "memoryPercent": 0.25},
                {"name": "jellyfin", "cpu": 2.0, "memory": 500 * 1024 * 1024, "memoryPercent": 2.5},
            ],
        }

        report = PulseReport(vitals=fake_vitals)
        self.assertEqual(report.cpu_temp, 46)
        self.assertEqual(report.temp_rating, "正常")
        self.assertEqual(report.running_count, 2)
        self.assertEqual(report.stopped_count, 1)
        self.assertIn("test-writer-helper", report.temporary_containers)
        
        soul_diag = report.generate_soul_diagnosis()
        self.assertIn("46℃", soul_diag)
        self.assertIn("气血极其充沛", soul_diag)
        self.assertIn("2盘全绿", soul_diag)

        data_dict = report.to_dict()
        self.assertEqual(data_dict["vital_signs"]["cpu_temp_c"], 46)
        self.assertEqual(data_dict["docker"]["running_count"], 2)
        self.assertIn("脉象极平，处于巅峰", soul_diag)

    def test_distressed_vitals_do_not_read_as_peak(self):
        distressed = {
            "cpu_util": {"user_load": 80, "system_load": 10},
            "mem_util": {"total_real": 8 * 1024 * 1024, "real_usage": 92, "cached": 1 * 1024 * 1024},
            "cpu_temp": 81,
            "vol_info": [{"total_size": 10 * (1024**4), "used_size": 9 * (1024**4)}],
            "hdd_info": [{"smart_status": "normal", "temp": 40}, {"smart_status": "warning", "temp": 48}],
            "sys_health": {"data": {"uptime": "24:00:00"}},
            "containers": [],
            "resources": [],
        }
        report = PulseReport(vitals=distressed)
        soul = report.generate_soul_diagnosis()
        self.assertNotIn("巅峰", soul)
        self.assertIn("脉象不稳", soul)
        self.assertIn("注意散热", soul)
        self.assertIn("气血大亏", soul)
        self.assertIn("疑似有损", soul)

        rendered = _render(report)
        self.assertIn("内存吃紧", rendered)
        self.assertIn("骨骼告警", rendered)
        self.assertIn("腹心胀满", rendered)
        self.assertNotIn("健康无异响", rendered)
        self.assertNotIn("胃口良好", rendered)

def _render(report: PulseReport) -> str:
    from rich.console import Console
    console = Console(record=True, width=120)
    report.render(console=console)
    return console.export_text()

if __name__ == "__main__":
    unittest.main()
