import logging
from datetime import date

from openg2p_registry_core.models import G2PRegisterChangeRequest
from openg2p_registry_core.services import G2PRegisterDomainService
from sqlalchemy.ext.asyncio import AsyncSession

from .domain_validation_utils import is_blank, parse_date, validation_error
from .utils.household_roster import (
    CHANGED_PERSON_KIND_MEMBER,
    recompute_household_for_ingested_row,
    recompute_households_for_change_request,
)

_logger = logging.getLogger("g2p-register-domain-service")

_ALLOWED_RELATIONSHIPS = {"CHILD", "SPOUSE", "OTHER"}


class G2PRegisterDomainServiceHouseholdMember(G2PRegisterDomainService):
    async def validate_domain_attributes(self, records: list[dict]):
        for record in records:
            self._validate_birth_date(record)
            self._validate_relationship_to_the_head(record)

    def _validate_birth_date(self, record: dict) -> None:
        birth_date = parse_date(record.get("birth_date"))
        if birth_date is not None and birth_date > date.today():
            validation_error("birth_date must not be in the future")

    def _validate_relationship_to_the_head(self, record: dict) -> None:
        value = record.get("relationship_to_the_head")
        if is_blank(value):
            return
        if str(value) not in _ALLOWED_RELATIONSHIPS:
            validation_error(
                "relationship_to_the_head must be one of CHILD, SPOUSE, OTHER"
            )

    def construct_search_text(self, payload: dict, extra: list[str] = None) -> str:
        _logger.info("Constructing search text for household member")

        keys = [
            "first_name",
            "last_name",
            "foundational_id",
            "middle_name",
            "given_name",
            "gender",
            "birth_date",
            "marital_status",
            "occupation",
            "education_level",
            "latitude",
            "longitude",
            "altitude",
            "plus_code",
            "address_line_1",
            "address_line_2",
            "postal_code",
            "country_code",
            "is_disabled",
            "is_head",
            "relationship_to_the_head",
        ]
        search_text = []
        if extra:
            search_text.extend(str(item).strip() for item in extra if str(item).strip())
        search_text.extend(
            str(payload.get(key) or "").strip()
            for key in keys
            if str(payload.get(key) or "").strip()
        )

        return " ".join(search_text).strip()

    def construct_record_name(self, payload: dict, extra: list[str] = None) -> str:
        _logger.info("Constructing record name for household member")

        keys = ["first_name", "last_name"]
        record_name = []
        if extra:
            record_name.extend(str(item).strip() for item in extra if str(item).strip())
        record_name.extend(
            str(payload.get(key) or "").strip()
            for key in keys
            if str(payload.get(key) or "").strip()
        )

        return " ".join(record_name).strip()

    async def pre_approve(self, change_request: G2PRegisterChangeRequest, session: AsyncSession):
        from ..models.household_member import G2PRegisterHouseholdMember

        await recompute_households_for_change_request(
            session,
            change_request,
            model=G2PRegisterHouseholdMember,
            changed_person_kind=CHANGED_PERSON_KIND_MEMBER,
        )

    async def post_ingest(self, register_id: str, register_row, session: AsyncSession):
        await recompute_household_for_ingested_row(session, register_row)
