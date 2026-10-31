from agent_blackbox import Recorder


def lookup_inventory(sku: str) -> dict:
    return {"sku": sku, "available": 24, "age_hours": 0}


with Recorder("inventory-investigation") as recorder:
    stock = recorder.call("inventory.lookup", lookup_inventory, sku="PUMP-042")

print(recorder.run.id)
