"""Run an existing deployment script/module under an NSXSwitch, without editing it.

  python -m nsx_testkit.run --mode fake --record calls.json --mocks gets.json deploy.py --its --args
  python -m nsx_testkit.run --mode real --capture-gets gets.json mypkg.deploy
"""
import argparse
import logging
import runpy
import sys

from .switch import Mode, NSXSwitch


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--mode", choices=[m.value for m in Mode], default="fake")
    parser.add_argument("--record", help="fake mode: write all transmitted API calls to this JSON file")
    parser.add_argument("--mocks", action="append", default=[], help="mock response file (repeatable)")
    parser.add_argument("--capture-gets", help="real mode: save real GET responses as a mock file")
    parser.add_argument("target", help="path to a .py script, or a module name")
    parser.add_argument("args", nargs=argparse.REMAINDER, help="arguments passed to the target")
    opts = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s")
    sys.argv = [opts.target, *opts.args]
    switch = NSXSwitch(opts.mode, record_to=opts.record, mocks=opts.mocks, capture_gets=opts.capture_gets)
    with switch:
        if opts.target.endswith(".py"):
            runpy.run_path(opts.target, run_name="__main__")
        else:
            runpy.run_module(opts.target, run_name="__main__", alter_sys=True)


if __name__ == "__main__":
    main()
