from app.services.relationship_extraction import (
    KIND_ANON,
    KIND_COMPETITOR,
    KIND_CUSTOMER,
    KIND_SUPPLIER,
    extract_own_mentions,
    extract_target_mentions,
    names_in,
)

DOC = (
    "Item 1. Business\n"
    'We design radio frequency chips. Our key customers include Amazon, Apple Inc. ("Apple"), '
    "Bose, and Cisco. Our competitors include Analog Devices, Broadcom, Qorvo, and Qualcomm. "
    "We purchase memory from SK Hynix Inc., Micron Technology, Inc., and Samsung. "
    "For example, NVIDIA relies on suppliers such as Taiwan Semiconductor Manufacturing Company. "
    "We engage with contract manufacturers such as Hon Hai Precision Industry Co., Ltd. and Fabrinet. "
    + "Filler sentence about products. "
    * 60
    + "\nItem 8. Financial Statements\n"
    "During fiscal 2025, fiscal 2024, and fiscal 2023, Apple, through sales to multiple distributors, "
    "contract manufacturers, and direct sales for multiple applications including smartphones, tablets, "
    "and watches, in the aggregate accounted for approximately 67%, 65%, and 66% of our net revenue. "
    "Direct sales to Amkor and Qualcomm accounted for 29.8% and 11.1% of our net sales. "
    "For fiscal year 2026, sales to one direct customer represented 22% of total revenue. "
    "Customer A and D accounted for 68% and 11% of accounts receivable, net, as of December 31, 2025. "
    "During 2025, the Company's net sales through its direct and indirect distribution channels "
    "accounted for 40% and 60%, respectively, of total net sales. " + "More filler. " * 60
)


def _by_kind(mentions):
    out: dict[str, list] = {}
    for m in mentions:
        out.setdefault(m.kind, []).append(m)
    return out


def test_own_mentions_cover_each_kind() -> None:
    kinds = _by_kind(extract_own_mentions(DOC, ["Skyworks"]))
    customers = {m.entity_text: m for m in kinds[KIND_CUSTOMER]}
    assert customers["Apple"].percent == 67.0 and customers["Apple"].basis == "revenue"
    assert (
        customers["Apple"].pattern == "customer_through" and customers["Apple"].section == "Item 8"
    )
    assert customers["Amkor"].percent == 29.8 and customers["Qualcomm"].percent == 11.1
    assert {"Amazon", "Apple Inc", "Bose", "Cisco"} <= set(customers)

    suppliers = {m.entity_text for m in kinds[KIND_SUPPLIER]}
    assert {
        "SK Hynix Inc",
        "Micron Technology",
        "Samsung",
        "Hon Hai Precision Industry Co",
        "Fabrinet",
    } <= suppliers
    assert "Taiwan Semiconductor Manufacturing Company" not in suppliers  # third-party statement

    competitors = {m.entity_text for m in kinds[KIND_COMPETITOR]}
    assert competitors == {"Analog Devices", "Broadcom", "Qorvo", "Qualcomm"}

    anon = {(m.label, m.percent, m.basis) for m in kinds[KIND_ANON]}
    assert ("one direct customer", 22.0, "revenue") in anon
    assert ("Customer A", 68.0, "receivables") in anon and (
        "Customer D",
        11.0,
        "receivables",
    ) in anon
    # distribution-channel percentages are not customers
    assert all("Company" not in (m.entity_text or "") for m in kinds[KIND_CUSTOMER])


def test_self_mentions_are_dropped() -> None:
    text = (
        "Item 1. Business\nWe sell vehicles produced by Ford Blue and Ford Model e. " + "x. " * 50
    )
    mentions = extract_own_mentions(text, ["Ford", "Ford Blue", "Ford Model e"])
    assert mentions == []


def test_target_mentions_classify_from_the_filers_view() -> None:
    mentions = extract_target_mentions(DOC, ["Apple", "Apple Inc"])
    kinds = {m.pattern: m for m in mentions}
    assert (
        kinds["customer_through"].kind == KIND_CUSTOMER
        and kinds["customer_through"].percent == 67.0
    )
    assert kinds["customer_list"].kind == KIND_CUSTOMER

    nvidia_doc = (
        "Item 1. Business\nAll of the GPUs used in our infrastructure today are NVIDIA GPUs. "
        "We compete with hyperscalers. " + "x. " * 50
    )
    got = extract_target_mentions(nvidia_doc, ["NVIDIA", "NVIDIA Corporation"])
    assert got and got[0].kind == KIND_SUPPLIER and got[0].pattern == "supply_cue"


def test_names_in_filters_generic_and_acronym_noise() -> None:
    assert names_in(
        "all major public and private cloud providers, AI model makers, OEMs, Intel Corporation, or Intel"
    ) == [
        "Intel Corporation",
        "Intel",
    ]
    assert names_in(
        "Advanced Micro Devices, Inc., or AMD, Huawei Technologies Co. Ltd., or Huawei"
    ) == [
        "Advanced Micro Devices",
        "AMD",
        "Huawei Technologies Co. Ltd",
        "Huawei",
    ]
