from locust import HttpUser, task, constant, events

class FastAPIUser(HttpUser):
    wait_time = constant(0)
    @task
    def health(self):
        with self.client.get("/health", catch_response=True) as r:
            if r.status_code != 200:
                r.failure("Healthcheck failed")
