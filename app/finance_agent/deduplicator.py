


from app.finance_agent.models import TransactionRecord


def split_duplicate_records(records: list[TransactionRecord],existing_hashes: set[str] | None = None,) -> tuple[list[TransactionRecord], list[TransactionRecord]]:
    #"""把交易记录拆分为新增记录和重复记录"""
    existing_hashes = existing_hashes or set()

    seen_hashes: set[str] = set()
    new_records: list[TransactionRecord] = []
    duplicate_records: list[TransactionRecord] = []

    for record in records:
        if record.raw_hash in existing_hashes or record.raw_hash in seen_hashes:
            duplicate_records.append(record)
            continue

        seen_hashes.add(record.raw_hash)
        new_records.append(record)

    return new_records, duplicate_records