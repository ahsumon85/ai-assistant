def main() -> None:
    from arq import run_worker

    from jobflow.workers.tasks import WorkerSettings

    run_worker(WorkerSettings)
