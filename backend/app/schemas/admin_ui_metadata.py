from pydantic import BaseModel


class AdminUiOptionItem(BaseModel):
    value: str
    label: str
    description: str | None = None


class AdminUiFieldMetadata(BaseModel):
    label: str
    description: str | None = None
    button_label: str | None = None
    modal_title: str | None = None
    placeholder: str | None = None
    options: list[AdminUiOptionItem] | None = None


class AdminUiSectionMetadata(BaseModel):
    title: str
    help_text: str | None = None
    fields: dict[str, AdminUiFieldMetadata]


class AdminUiMetadataResponse(BaseModel):
    axes: AdminUiSectionMetadata
    capabilities: AdminUiSectionMetadata
    recommendations: AdminUiSectionMetadata
