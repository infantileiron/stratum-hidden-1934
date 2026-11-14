from src.services import ingest_batch as service
def list_items():return service.list_batches()
def detail(id):return service.detail(id)
def create(data):return service.create_batch(data)
def receive(id,data):return service.receive_fragment(id,data)
def seal(id):return service.seal_batch(id)
def publish(id):return service.publish_batch(id)
