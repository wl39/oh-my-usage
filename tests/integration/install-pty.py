"""Run only in a disposable Linux container after install-linux.sh setup."""
import os
import fcntl
from pathlib import Path
import pty
import select
import subprocess
import struct
import termios
import time

rc = Path(os.environ["HOME"]) / ".zshrc"
with rc.open("a") as stream:
    stream.write("\nPROMPT='OMU_INSTALL_READY> '\n")
master, slave = pty.openpty()
fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 24, 100, 0, 0))
process = subprocess.Popen(["/src/install.sh"], stdin=slave, stdout=slave, stderr=slave,
                           cwd="/src", env=dict(os.environ, TERM="xterm", NO_COLOR="1"))
os.close(slave)
output = b""
sent = False
try:
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        if select.select([master], [], [], 0.2)[0]:
            try:
                output += os.read(master, 65536)
            except OSError:
                break
        if not sent and b"OMU_INSTALL_READY> " in output:
            # Wait for the actual prompt; zsh can discard input queued during startup.
            os.write(master, b"oh-my-usage --version > /tmp/omu-pty-version; whence -w oh-my-usage > /tmp/omu-pty-function; exit\n")
            sent = True
        if process.poll() is not None:
            break
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        raise AssertionError("Installer did not reach a usable prompt: " + output.decode(errors="replace"))
    assert process.returncode == 0, output.decode(errors="replace")
    assert sent, output.decode(errors="replace")
    assert b"Opening your configured zsh now" in output
    assert Path('/tmp/omu-pty-version').read_text().strip()
    assert 'function' in Path('/tmp/omu-pty-function').read_text()
    print('PASS: ./install.sh automatically entered zsh with the command loaded')
finally:
    if process.poll() is None:
        process.kill()
        process.wait()
    os.close(master)
