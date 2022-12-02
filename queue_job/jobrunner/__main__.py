import odoo

from . import QueueJobRunnerThread


def main():
    odoo.tools.config.parse_config()
    runner_thread = QueueJobRunnerThread()
    runner_thread.runner.run()


if __name__ == "__main__":
    main()
