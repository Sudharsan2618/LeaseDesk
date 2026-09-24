"""Phase 1 — reference-data model (generic domain). Proves the taxonomy loads, PKW is active and
maps to the DE_PKW_V1 policy, the future asset categories are declared, and a fresh Offer records
its selection seeded to the representative PKW product (spec §3.5-3.6, §9.5)."""
from app.core.policy import load_policy
from app.core.types import FieldStatus
from app.domain.entities import Offer
from app.domain.reference import (
    DEFAULT_ASSET_CATEGORY,
    DEFAULT_BUSINESS_LINE,
    DEFAULT_PRODUCT,
    load_reference_data,
)


def test_reference_data_loads_with_all_asset_categories():
    ref = load_reference_data()
    keys = {c.key for c in ref.asset_categories}
    assert keys == {"PKW", "Equipment", "NFZ", "ITK"}          # spec §3.6 — asset-agnostic
    pkw = ref.asset_category("PKW")
    assert pkw and pkw.is_active and pkw.attribute_schema        # PKW fully modelled
    assert all(not ref.asset_category(k).is_active for k in ("Equipment", "NFZ", "ITK"))  # declared, planned


def test_pkw_product_maps_to_de_pkw_v1_policy():
    ref = load_reference_data()
    prod = ref.product(DEFAULT_PRODUCT)
    assert prod and prod.is_active
    assert prod.business_line == DEFAULT_BUSINESS_LINE
    assert prod.asset_category == DEFAULT_ASSET_CATEGORY
    # the product's parameters ARE the existing policy — engine stays unchanged
    assert prod.policy_id == "DE_PKW_V1"
    assert ref.policy_id_for_product(DEFAULT_PRODUCT) == load_policy("DE_PKW_V1").policy_id


def test_business_line_lists_its_products():
    ref = load_reference_data()
    prods = ref.products_for(DEFAULT_BUSINESS_LINE)
    assert DEFAULT_PRODUCT in {p.key for p in prods}


def test_new_offer_records_seeded_selection():
    offer = Offer(reference="OFF-ref-test")
    assert offer.leasing_product_key.value == DEFAULT_PRODUCT
    assert offer.asset_category_key.value == DEFAULT_ASSET_CATEGORY
    assert offer.business_line_key.status == FieldStatus.ESTABLISHED
    # product's policy_id must match the key the engine actually loads
    ref = load_reference_data()
    assert ref.policy_id_for_product(offer.leasing_product_key.value) == offer.policy_version


def test_pkw_has_filterable_attributes_for_general_extraction():
    # Phase 3 needs filterable attributes (e.g. seats) to narrow the catalogue from free text.
    ref = load_reference_data()
    filters = {a.key for a in ref.asset_category("PKW").filters()}
    assert {"seats", "fuel_type", "make"} <= filters
