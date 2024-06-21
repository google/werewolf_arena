from werewolf.runner import run
from absl import app as absl_app


def main(_):
    run()


if __name__ == "__main__":
    absl_app.run(main)
