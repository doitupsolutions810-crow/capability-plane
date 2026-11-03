import concurrent.futures
from contextlib import closing
import pathlib
import sqlite3
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from admin.durable_outbox import DurableOutbox, OutboxConflict, OutboxError, OutboxLeaseLost, jetstream_publish_fn

class OutboxTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db=pathlib.Path(self.tmp.name)/'outbox.sqlite3'
        self.o=DurableOutbox(self.db)

    def test_enqueue_idempotent_and_restart(self):
        a=self.o.enqueue('job-1','queued',{'x':1})
        b=DurableOutbox(self.db).enqueue('job-1','queued',{'x':1})
        self.assertEqual(a.id,b.id)
        self.assertEqual(self.o.unpublished_count(),1)

    def test_conflicting_payload_rejected(self):
        self.o.enqueue('j','enqueue',{'status':'queued'})
        with self.assertRaises(OutboxConflict):
            self.o.enqueue('j','enqueue',{'status':'completed'})
        self.assertEqual(self.o.unpublished_count(),1)

    def test_corrupt_payload_refuses_old_success(self):
        self.o.enqueue('j','enqueue',{'ok':True})
        with closing(sqlite3.connect(self.db)) as c:
            c.execute("UPDATE outbox_events SET payload='not json'")
            c.commit()
        with self.assertRaises(OutboxError):
            self.o.enqueue('j','enqueue',{'ok':True})

    def test_claim_is_exclusive_across_independent_connections(self):
        for i in range(80):
            self.o.enqueue('j'+str(i),'queued',{'n':i})
        barrier=threading.Barrier(8)
        def claim(_):
            barrier.wait()
            return [x.id for x in DurableOutbox(self.db).claim_batch(limit=25)]
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as p:
            results=list(p.map(claim,range(8)))
        flat=[x for r in results for x in r]
        self.assertEqual(len(flat),80)
        self.assertEqual(len(set(flat)),80)

    def test_lease_owner_required(self):
        a=self.o.enqueue('j','queued',{'x':1})
        claimed=self.o.claim_batch()[0]
        with self.assertRaises(OutboxLeaseLost):
            self.o.mark_published(a.id)
        with self.assertRaises(OutboxLeaseLost):
            self.o.mark_published(a.id,'wrong')
        self.assertTrue(self.o.mark_published(a.id,claimed.claim_token))
        self.assertEqual(self.o.unpublished_count(),0)

    def test_lease_expiration_and_stale_completion(self):
        self.o.enqueue('j','queued',{'x':1})
        now=time.time()
        with patch('admin.durable_outbox.time.time',return_value=now):
            first=self.o.claim_batch(lease_seconds=1)[0]
        with patch('admin.durable_outbox.time.time',return_value=now+2):
            second=self.o.claim_batch(lease_seconds=20)[0]
            with self.assertRaises(OutboxLeaseLost):
                self.o.mark_published(first.id,first.claim_token)
            self.o.mark_published(second.id,second.claim_token)
        self.assertEqual(self.o.unpublished_count(),0)

    def test_ambiguous_ack_stays_pending(self):
        self.o.enqueue('j','queued',{'x':1})
        self.assertEqual(self.o.relay_once(lambda event:None),0)
        self.assertEqual(self.o.unpublished_count(),1)
        with closing(sqlite3.connect(self.db)) as c:
            attempts=c.execute('SELECT attempt_count FROM outbox_events').fetchone()[0]
        self.assertEqual(attempts,1)

    def test_explicit_ack_and_restart(self):
        self.o.enqueue('j','queued',{'x':1})
        seen=[]
        self.assertEqual(self.o.relay_once(lambda event:(seen.append(event.id) or True)),1)
        self.assertEqual(DurableOutbox(self.db).unpublished_count(),0)
        self.assertEqual(len(seen),1)

    def test_relay_cannot_fake_jetstream(self):
        with self.assertRaises(OutboxError):
            jetstream_publish_fn()
        self.o.enqueue('j','queued',{'x':1})
        delivery=[]
        transport=jetstream_publish_fn(transport=lambda subject,payload:(delivery.append((subject,payload)) or True))
        self.assertEqual(self.o.relay_once(transport),1)
        self.assertEqual(delivery[0][1]['event_id'] is not None,True)

    def test_subject_wildcard_never_reaches_transport(self):
        with self.assertRaises(OutboxError):
            jetstream_publish_fn('admin.>', transport=lambda subject,payload: True)
        self.o.enqueue('j','danger.*',{'x':1})
        calls=[]
        pub=jetstream_publish_fn(transport=lambda subject,payload: calls.append(subject) or True)
        self.assertEqual(self.o.relay_once(pub),0)
        self.assertEqual(calls,[])
        self.assertEqual(self.o.unpublished_count(),1)

    def test_duplicate_concurrent_enqueue_single_record(self):
        barrier=threading.Barrier(10)
        def worker(i):
            barrier.wait()
            return DurableOutbox(self.db).enqueue('same','queued',{'x':1}).id
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as p:
            results=list(p.map(worker,range(10)))
        self.assertEqual(len(set(results)),1)

    def test_malformed_json_and_limits(self):
        for val in ({'x':float('nan')},{'x':float('inf')},{'huge':'x'*66000},[],{} if False else {'x':set([1])}):
            with self.assertRaises(ValueError): self.o.enqueue('j','queued',val)
        for bad in (0,True,1001,-1):
            with self.assertRaises(ValueError):self.o.claim_batch(limit=bad)

    def test_migration_from_legacy_schema(self):
        legacy=pathlib.Path(self.tmp.name)/'old.sqlite3'
        with closing(sqlite3.connect(legacy)) as c:
            c.execute('''CREATE TABLE outbox_events(id TEXT PRIMARY KEY, aggregate_id TEXT NOT NULL,event_type TEXT NOT NULL,payload TEXT NOT NULL,created_at REAL NOT NULL,published_at REAL,attempt_count INTEGER NOT NULL DEFAULT 0,next_attempt_at REAL NOT NULL,last_error TEXT,UNIQUE(event_type,aggregate_id))''')
            c.execute("INSERT INTO outbox_events(id,aggregate_id,event_type,payload,created_at,next_attempt_at) VALUES('a','j','queued','{\"n\":1}',1,1)")
            c.commit()
        restored=DurableOutbox(legacy)
        items=restored.claim_batch()
        self.assertEqual(len(items),1)
        self.assertTrue(items[0].claim_token)

if __name__=='__main__': unittest.main()
