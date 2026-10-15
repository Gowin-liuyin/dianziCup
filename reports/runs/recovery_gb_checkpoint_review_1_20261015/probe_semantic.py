import hashlib
import json
import math
import multiprocessing
from pathlib import Path
import time
from ai_intel.infrastructure.models.semantic import LocalSemanticModels,E5_MODEL,RERANK_MODEL

def main():
    cache = Path('C:/Users/yinha/.codex/cache/dianzi/r05-semantic-runtime')
    artifacts = []
    for model in (E5_MODEL,RERANK_MODEL):
        for item in model.artifacts:
            path = cache / model.folder / item.relative_path
            assert path.stat().st_size == item.size
            with path.open('rb') as content:
                actual_hash = hashlib.file_digest(content,'sha256').hexdigest()
            assert actual_hash == item.sha256
            artifacts.append({'folder':model.folder,'path':item.relative_path,'size':item.size,'sha256':actual_hash})
    models = LocalSemanticModels(cache)
    passages = ('权限撤销后，服务器必须重新验证当前认证会话。','A garden contains flowers and trees.')
    started = time.perf_counter()
    query = models.embed_query('撤销会话后如何保证权限？')
    vectors = models.embed_passages(passages)
    ranked = models.rerank('撤销会话后如何保证权限？',passages)
    assert query.dimension == vectors.dimension == 384
    assert len(query.vectors) == 1 and len(vectors.vectors) == 2
    assert query.model_version == vectors.model_version == E5_MODEL.model_version
    assert ranked.model_version == RERANK_MODEL.model_version
    assert sorted(item.index for item in ranked.items) == [0,1]
    assert all(math.isfinite(item.score) for item in ranked.items)
    assert not multiprocessing.active_children()
    result = {'artifacts':artifacts,'query_dimension':query.dimension,'passage_count':len(vectors.vectors),'query_l2':math.sqrt(sum(value*value for value in query.vectors[0])),'rerank_indices':[item.index for item in ranked.items],'rerank_scores':[item.score for item in ranked.items],'elapsed_seconds':time.perf_counter()-started,'active_children_after':0,'paid_calls':0,'downloads':0,'quality_evaluation':'not_run'}
    (Path(__file__).parent / 'semantic_smoke.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False))

if __name__ == '__main__':
    main()
