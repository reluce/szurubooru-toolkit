import threading

from szurubooru_toolkit import utils
from szurubooru_toolkit.utils import invoke_gallery_dl


class FakeRun:
    def __init__(self, barrier=None):
        self.commands = []
        self.lock = threading.Lock()
        self.barrier = barrier

    def __call__(self, command):
        with self.lock:
            self.commands.append(command)
        if self.barrier:
            self.barrier.wait()


def test_single_url_runs_one_process(monkeypatch, tmp_path):
    fake = FakeRun()
    monkeypatch.setattr(utils.subprocess, 'run', fake)

    download_dir = invoke_gallery_dl(['https://example.com/a'], str(tmp_path), ['-q'], workers=4)

    assert len(fake.commands) == 1
    assert fake.commands[0][0] == 'gallery-dl'
    assert f'-D={download_dir}' in fake.commands[0]
    assert '-q' in fake.commands[0]
    assert fake.commands[0][-1] == 'https://example.com/a'


def test_multiple_urls_fan_out_concurrently(monkeypatch, tmp_path):
    # The barrier only passes if both gallery-dl processes run at the same time
    fake = FakeRun(barrier=threading.Barrier(2, timeout=5))
    monkeypatch.setattr(utils.subprocess, 'run', fake)

    urls = ['https://example.com/a', 'https://example.com/b']
    download_dir = invoke_gallery_dl(urls, str(tmp_path), workers=2)

    assert len(fake.commands) == 2
    # Every process downloads into the same shared directory
    assert all(f'-D={download_dir}' in command for command in fake.commands)
    assert sorted(command[-1] for command in fake.commands) == urls


def test_multiple_urls_with_one_worker_stay_sequential(monkeypatch, tmp_path):
    fake = FakeRun()
    monkeypatch.setattr(utils.subprocess, 'run', fake)

    urls = ['https://example.com/a', 'https://example.com/b']
    invoke_gallery_dl(urls, str(tmp_path), workers=1)

    # One process with both URLs, like before
    assert len(fake.commands) == 1
    assert fake.commands[0][-2:] == urls
