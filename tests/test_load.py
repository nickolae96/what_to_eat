
def test_health_endpoint_under_load():
    import subprocess, sys

    cmd = [
        sys.executable, "-m", "locust",
        "-f", "locustfile.py",
        "--host=http://127.0.0.1:8000",
        "--headless",
        "-u", "20",
        "-r", "2",
        "--run-time", "20s",
        "--only-summary",
    ]

    result = subprocess.run(cmd)
    print(result.stdout)
    assert result.returncode == 0