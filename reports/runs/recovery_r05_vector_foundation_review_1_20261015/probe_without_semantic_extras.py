"""A stdlib-only child must report missing runtime, keep capacity and never return an answer."""

import importlib.util
import multiprocessing
from pathlib import Path

from ai_intel.infrastructure.models.clients import ModelNotConfiguredError
from ai_intel.infrastructure.models.semantic import LocalSemanticModels

if __name__ == '__main__':
    assert importlib.util.find_spec('onnxruntime') is None
    assert importlib.util.find_spec('tokenizers') is None
    assert importlib.util.find_spec('numpy') is None
    previous = len(multiprocessing.active_children())
    models = LocalSemanticModels(Path('C:/Users/yinha/.codex/cache/dianzi/r05-semantic-runtime'))
    try:
        models.embed_query('缺少语义运行库时不得伪成功')
    except ModelNotConfiguredError as error:
        assert str(error) == 'verified local model or runtime unavailable'
    else:
        raise AssertionError('missing semantic runtime returned a successful result')
    assert len(multiprocessing.active_children()) == previous
    print('PASS: stdlib-only missing extras raise ModelNotConfiguredError and leave no active child')
