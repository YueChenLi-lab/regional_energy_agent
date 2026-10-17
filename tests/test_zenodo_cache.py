"""Artificial archive transport fixtures; actual archive checksums are in docs evidence."""
import hashlib
import io
import json
import zipfile

import httpx
import pytest

from energy_agent import adapters


def test_formal_archive_checksum_license_members_and_offline_replay(tmp_path,monkeypatch):
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w') as z:
        z.writestr('test_building/test_building_records.csv','Time,Type,Record\n2017-01-01 00:00:00,Q,2\n')
        z.writestr('README.md','ARTIFICIAL FIXTURE; not a real archive')
    archive=stream.getvalue()
    metadata={'id':6590976,'metadata':{'license':{'id':'cc-by-4.0'}},'files':[{'key':'dataset_v2.zip',
        'checksum':'md5:'+hashlib.md5(archive).hexdigest(),
        'links':{'self':'https://zenodo.org/api/records/6590976/files/dataset_v2.zip/content'}}]}
    client=httpx.Client(transport=httpx.MockTransport(lambda r:httpx.Response(200,content=archive if str(r.url).endswith('/content') else json.dumps(metadata).encode())))
    real_fetch=adapters.fetch_cached
    monkeypatch.setattr(adapters,'fetch_cached',lambda url,cache_dir,**kw:real_fetch(url,cache_dir,client=client,**kw))
    path,artifact,docs=adapters.fetch_zenodo_energydetective(cache_dir=tmp_path,offline=False)
    assert artifact.sha256==hashlib.sha256(path.read_bytes()).hexdigest()
    assert artifact.container_sha256==hashlib.sha256(archive).hexdigest()
    assert artifact.member_path=='test_building/test_building_records.csv'
    assert artifact.license_id==docs.license_id=='CC-BY-4.0'
    assert adapters.fetch_zenodo_energydetective(cache_dir=tmp_path,offline=True)[1]==artifact
    metadata['files'][0]['checksum']='md5:'+'0'*32
    bad_cache=tmp_path/'bad'
    with pytest.raises(ValueError,match='发布校验值不符'):
        adapters.fetch_zenodo_energydetective(cache_dir=bad_cache,offline=False)
