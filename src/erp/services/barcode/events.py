from typing import Any

import boto3

from erp.api.modules.item.schemas import ItemBarcode
from erp.core.config import get_settings


def send_barcode_generation_event(data: ItemBarcode) -> dict[str, Any]:
    settings = get_settings()

    sqs_client = boto3.client(
        "sqs",
        region_name=settings.AWS_REGION,
    )

    return sqs_client.send_message(
        QueueUrl=settings.BARCODE_GENERATION_SQS_QUEUE_URL,
        MessageBody=data.model_dump_json(),
    )
