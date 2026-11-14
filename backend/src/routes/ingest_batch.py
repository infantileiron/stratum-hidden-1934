from fastapi import APIRouter,Depends
from src.controllers import ingest_batch as controller
from src.schemas.entities import BatchInput,FragmentInput
from src.services.auth import current,editor
router=APIRouter(prefix='/ingest-batches',tags=['ingest-batches'])
@router.get('')
def list_items(user=Depends(current)):return controller.list_items()
@router.post('',status_code=201)
def create(data:BatchInput,user=Depends(editor)):return controller.create(data)
@router.get('/{id}')
def detail(id:str,user=Depends(current)):return controller.detail(id)
@router.post('/{id}/fragments',status_code=201)
def receive(id:str,data:FragmentInput,user=Depends(editor)):return controller.receive(id,data)
@router.post('/{id}/seal')
def seal(id:str,user=Depends(editor)):return controller.seal(id)
@router.post('/{id}/publish',status_code=201)
def publish(id:str,user=Depends(editor)):return controller.publish(id)
