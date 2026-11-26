"""Validated provider payloads, independent of local clinical criteria."""
from typing import Annotated
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, StrictStr

Text = Annotated[StrictStr, Field(min_length=1, max_length=500)]
SCTID = Annotated[StrictStr, Field(pattern=r"^[0-9]{6,18}$")]

class ProviderModel(BaseModel):
    model_config = ConfigDict(extra="allow")

class GeneticPathology(ProviderModel):
    codigo: Text
    nombre: Text
    genes: list[Text]
    herencia: Text
    de_grupo: StrictBool = False

class CDSSSummary(ProviderModel):
    codigo: Text
    nombre: Text

class CDSSSymptom(ProviderModel):
    snomed_codigo: SCTID
    termino: Text
    es_cardinal: StrictBool

class CDSSPathology(CDSSSummary):
    sintomas: list[CDSSSymptom]

class CDSSRank(ProviderModel):
    codigo: Text
    puntaje: StrictInt
    cardinales_coincidentes: Annotated[StrictInt, Field(ge=0)]
    sintomas_coincidentes: Annotated[StrictInt, Field(ge=0)]

class CDSSAdvice(ProviderModel):
    compatible: StrictBool
    estrategia: Text
    patologias: list[CDSSSummary]
    ranking: list[CDSSRank]
    mensaje: StrictStr | None = None
