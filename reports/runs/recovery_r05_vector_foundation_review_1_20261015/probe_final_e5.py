"""One real E5 query verifies the repaired shared validator on normalized model output."""

import json
import math
import multiprocessing
import os
import time
from pathlib import Path

from ai_intel.infrastructure.models.semantic import E5_MODEL, LocalSemanticModels

if __name__ == '__main__':
    before = len(multiprocessing.active_children())
    client = LocalSemanticModels(Path(os.environ['R05_SEMANTIC_CACHE']))
    start = time.monotonic()
    result = client.embed_query('提示注入为什么会改变语言模型的行为？')
    elapsed = time.monotonic() - start
    assert result.model_version == E5_MODEL.model_version
    assert result.dimension == 384 and len(result.vectors) == 1
    assert all(type(coordinate) is float and math.isfinite(coordinate) for coordinate in result.vectors[0])
    norm = math.sqrt(math.fsum(coordinate * coordinate for coordinate in result.vectors[0]))
    assert math.isclose(norm, 1.0, abs_tol=1e-5)
    assert len(multiprocessing.active_children()) == before
    print(json.dumps({'kind': 'real_e5_norm_repair_target', 'model_version': result.model_version,
                      'dimension': result.dimension, 'count': len(result.vectors), 'l2_norm': norm,
                      'total_seconds': elapsed, 'active_children_before_after': before}, ensure_ascii=False))
