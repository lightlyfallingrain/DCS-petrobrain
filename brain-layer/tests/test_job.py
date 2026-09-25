from __future__ import annotations

from job import Job, JobSlot, ReplyQueue


def test_job_slot_first_submit_is_current() -> None:
    slot = JobSlot()
    generation = slot.submit(Job(utterance_id="U1", payload={}))
    assert slot.is_current(generation)


def test_job_slot_newer_submit_supersedes_older() -> None:
    slot = JobSlot()
    first = slot.submit(Job(utterance_id="U1", payload={}))
    second = slot.submit(Job(utterance_id="U2", payload={}))
    assert not slot.is_current(first)
    assert slot.is_current(second)


def test_reply_queue_push_and_drain_all_oldest_first() -> None:
    queue = ReplyQueue()
    queue.push({"utterance_id": "U1"})
    queue.push({"utterance_id": "U2"})
    assert queue.drain_all() == [{"utterance_id": "U1"}, {"utterance_id": "U2"}]


def test_reply_queue_drain_all_empties_the_queue() -> None:
    queue = ReplyQueue()
    queue.push({"utterance_id": "U1"})
    queue.drain_all()
    assert queue.drain_all() == []
