from szurubooru_toolkit.relations import RelationsBatch
from szurubooru_toolkit.relations import cluster


def test_cluster_transitive_chain():
    # 1-2 and 2-3 are similar, 1-3 was never directly linked
    assert cluster([(1, 2), (2, 3)]) == [{1, 2, 3}]


def test_cluster_separate_components():
    clusters = cluster([(1, 2), (10, 11), (11, 12)])

    assert sorted(clusters, key=min) == [{1, 2}, {10, 11, 12}]


def test_cluster_empty():
    assert cluster([]) == []


def test_cluster_long_chain():
    # The exact scenario from sequential uploads: every post only knows its predecessors
    edges = []
    for i in range(2, 11):
        edges.append((i, i - 1))

    assert cluster(edges) == [set(range(1, 11))]


class FakeSzuru:
    """Records update_post_relations calls; returns True (updated) per call."""

    def __init__(self, fail_ids=()):
        self.calls = []
        self.fail_ids = set(fail_ids)

    def update_post_relations(self, post_id, relation_ids):
        if post_id in self.fail_ids:
            raise RuntimeError('boom')
        self.calls.append((post_id, set(relation_ids)))
        return True


def test_batch_reconcile_writes_full_member_list():
    batch = RelationsBatch()
    # Sequential upload scenario: post 102 saw 101, post 103 saw 101 and 102
    batch.add(102, [101])
    batch.add(103, [101, 102])

    fake = FakeSzuru()
    updated = batch.reconcile(fake)

    assert updated == 3
    assert dict(fake.calls) == {
        101: {102, 103},
        102: {101, 103},
        103: {101, 102},
    }


def test_batch_reconcile_no_edges():
    assert RelationsBatch().reconcile(FakeSzuru()) == 0


def test_batch_reconcile_continues_after_error():
    batch = RelationsBatch()
    batch.add(2, [1])
    batch.add(3, [1, 2])

    fake = FakeSzuru(fail_ids={1})
    updated = batch.reconcile(fake)

    # Post 1 failed, the other two must still be updated
    assert updated == 2
    assert {call[0] for call in fake.calls} == {2, 3}


def test_batch_add_accepts_string_ids():
    batch = RelationsBatch()
    batch.add('2', ['1'])

    assert batch.edges == [(2, 1)]
