from dataclasses import dataclass,field
from typing import Any
@dataclass
class BoreholeDataset:
 id:str
 name:str
 source:str
 rows:list[dict]
 created_at:str=''
@dataclass
class StateModel:
 id:str
 name:str
 config:dict
 revision:int=1
 created_at:str=''
@dataclass
class SequenceStudy:
 id:str
 name:str
 dataset_id:str
 model_id:str
 borehole:str
 snapshot:dict
 checksum:str
 created_at:str=''
@dataclass
class DecodeRun:
 id:str
 study_id:str
 status:str='queued'
 result:dict[str,Any]=field(default_factory=dict)
 error:str=''
 created_at:str=''
@dataclass
class LayerReview:
 id:str
 run_id:str
 comment:str
 status:str='pending'
 reviewer:str=''
 created_at:str=''
@dataclass
class Report:
 id:str
 run_id:str
 review_id:str
 title:str
 created_at:str=''
@dataclass
class IngestBatch:
 id:str
 name:str
 source:str
 status:str='receiving'
 expected_fragments:int=0
 boreholes:list[str]=field(default_factory=list)
 sealed_at:str=''
 published_at:str=''
 dataset_id:str=''
 created_at:str=''
@dataclass
class IngestFragment:
 id:str
 batch_id:str
 fragment_no:int
 status:str
 checksum:str
 reason:str=''
 row_count:int=0
 accepted_rows:int=0
 duplicate_rows:int=0
 boreholes:list[str]=field(default_factory=list)
 depth_min:float|None=None
 depth_max:float|None=None
 received_at:str=''
 payload_rows:str=''
