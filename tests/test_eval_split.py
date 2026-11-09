from eval.split import SampleItem, assign_split


def test_reserva_por_grupos():
    items = [SampleItem(f"p{i}", "pdf", "es", 1) for i in range(11)] + [SampleItem("d1", "doc", "es", 1), SampleItem("d2", "doc", "es", 1), SampleItem("e1", "pdf", "en", 1), SampleItem("c1", "pdf", "es", 2)]
    split = assign_split(items, seed=7)
    reserva = {k for k, v in split.items() if v == "reserve"}
    assert len(reserva) == 5 and reserva & {"d1", "d2"} and "e1" in reserva and "c1" in reserva
    assert split == assign_split(items, seed=7)
    assert set(split.values()) == {"tuning", "reserve"} and len(split) == 15


def test_muestra_vacia():
    assert assign_split([], seed=1) == {}
