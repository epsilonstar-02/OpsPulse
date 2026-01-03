import pathway as pw
import argparse

# ================= Kafka / Redpanda Config =================
KAFKA_CONF = {
    "bootstrap.servers": "d5c2s6rrcoacstisf5a0.any.ap-south-1.mpx.prd.cloud.redpanda.com:9092",
    "security.protocol": "SASL_SSL",
    "sasl.mechanisms": "SCRAM-SHA-256",
    "sasl.username": "ashutosh",
    "sasl.password": "768581",
    "group.id": "opspulse-consumer",
    "auto.offset.reset": "earliest",
    "enable.auto.commit": True,
}

TOPIC = "raw_logs"

# ================= Schema =================
class LogSchema(pw.Schema):
    # REQUIRED FIELDS
    timestamp: str
    level: str
    source: str
    service: str
    message: str

    # OPTIONAL COMMON LOG FIELDS
    request_id: str | None
    user_id: str | None
    ip_address: str | None
    endpoint: str | None
    method: str | None
    status_code: int | None
    response_time_ms: float | None

    # ANOMALY LABELS
    _labels: dict | None

    # 🔴 CRITICAL FIX
    class Meta:
        allow_extra_columns = True


# ================= Pipeline =================
def create_pipeline(topic: str, rdkafka_settings: dict):

    logs = pw.io.kafka.read(
        servers=rdkafka_settings["bootstrap.servers"],
        topic=topic,
        rdkafka_settings=rdkafka_settings,
        schema=LogSchema,
        format="json",
    )

    enriched = logs.with_columns(
        partition=pw.col("pw.partition"),
        offset=pw.col("pw.offset"),

        is_anomaly=pw.if_else(
            pw.col("_labels").is_not_none(),
            pw.col("_labels")["is_anomaly"],
            False,
        ),

        anomaly_type=pw.if_else(
            pw.col("_labels").is_not_none(),
            pw.col("_labels")["anomaly_type"],
            "none",
        ),

        anomaly_score=pw.if_else(
            pw.col("_labels").is_not_none(),
            pw.col("_labels")["anomaly_score"],
            0.0,
        ),
    )

    # 🔥 PRINT RAW PRODUCER DATA
    pw.debug.compute_and_print(
        enriched,
        title="📥 LIVE LOGS FROM REDPANDA (PRODUCER PAYLOAD)",
        line_limit=20,
    )

    return enriched


# ================= Main =================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="OpsPulse Pathway Kafka Consumer")
    parser.add_argument("--topic", default=TOPIC)
    parser.add_argument("--group-id", default="opspulse-consumer")
    args = parser.parse_args()

    KAFKA_CONF["group.id"] = args.group_id

    print("🚀 Starting Pathway Consumer")
    print(f"   Topic    : {args.topic}")
    print(f"   Group ID : {args.group_id}")
    print("   Waiting for Kafka messages...\n")

    # MUST CREATE PIPELINE FIRST
    create_pipeline(args.topic, KAFKA_CONF)

    # START PATHWAY
    pw.run()
