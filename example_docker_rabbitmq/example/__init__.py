import docker
import logging
from time import sleep

from celery_worker_on_demand import CeleryWorkerOnDemand
from celery_worker_on_demand import Agent
from celery_worker_on_demand import UpWorker
from celery_worker_on_demand import DownWorker

from .celery_app import celery_app  # noqa:F401
from . import tasks  # noqa:F401


logger = logging.getLogger('test-docker')

docker_client = docker.DockerClient(base_url='unix://var/run/docker.sock')
CONTAINERS = {}


class MyAgent(Agent):
    def flag_down(self, queue):
        return super().flag_down(queue) and CONTAINERS.get(queue.name)


class MyUpWorker(UpWorker):
    def run(self):
        container = CONTAINERS.get(self.queue.name)
        if container:
            container.start()
        else:
            container = docker_client.containers.run(
                'cwod-example-docker-rabbitmq:latest',
                entrypoint='celery -A example worker -l INFO -Q ' +
                           f'{self.queue.name} -E',
                environment={
                    'BROKER': 'amqp://cwod:cwod@rabbit:5672/rabbit',
                    'BACKEND': 'amqp://cwod:cwod@rabbit:5672/rabbit',
                },
                network='cwod-example-docker-rabbitmq',
                detach=True,
            )
            CONTAINERS[self.queue.name] = container
        while not self.queue.has_worker:
            container.reload()
            logger.debug(f'container.status is: {container.status}')
            sleep(1)


class MyDownWorker(DownWorker):
    def run(self):
        CONTAINERS[self.queue.name].stop()


class MyCeleryWorkerOnDemand(CeleryWorkerOnDemand):
    Agent = MyAgent
    UpWorker = MyUpWorker
    DownWorker = MyDownWorker
