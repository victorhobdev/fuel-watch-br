section Section1;

shared p_inject_invalid = false meta [IsParameterQuery = true, Type = "Logical", IsParameterQueryRequired = true];

[DataDestinations = {[Definition = [Kind = "Reference", QueryName = "lab_m06_municipios_DataDestination", IsNewTarget = true], Settings = [Kind = "Automatic", TypeSettings = [Kind = "Table"]]]}]
shared lab_m06_municipios =
let
    Catalog = Lakehouse.Contents([]),
    Workspace = Catalog{[workspaceId = "{{WORKSPACE_ID}}"]}[Data],
    Lake = Workspace{[lakehouseId = "{{LAKEHOUSE_ID}}"]}[Data],
    Reference = Lake{[Id = "ref_municipio_ibge", ItemKind = "Table"]}[Data],
    Approved = Table.SelectRows(Reference, each [ibge_sha256] = "2338ca0e4f482e065e14d1aec04d69ba525ba69ec4cc103161f6cb178163dad0"),
    Projection = Table.SelectColumns(Approved, {"municipio_ibge", "nome", "uf"}),
    Typed = Table.TransformColumnTypes(Projection, {{"municipio_ibge", type text}, {"nome", type text}, {"uf", type text}}),
    Trimmed = Table.TransformColumns(Typed, {{"municipio_ibge", Text.Trim, type text}, {"nome", Text.Trim, type text}, {"uf", Text.Trim, type text}}),
    Fixture = #table(type table [municipio_ibge = text, nome = text, uf = text], {{"INVALID", "M06_SYNTHETIC_INVALID", "RJ"}}),
    Candidate = if p_inject_invalid then Table.Combine({Trimmed, Fixture}) else Trimmed,
    Invalid = Table.SelectRows(Candidate, each [municipio_ibge] = null or Text.Length([municipio_ibge]) <> 7 or Text.Select([municipio_ibge], {"0".."9"}) <> [municipio_ibge] or [uf] <> "RJ" or [nome] = null or [nome] = ""),
    Checked = if Table.RowCount(Candidate) <> 92 or Table.RowCount(Table.Distinct(Candidate, {"municipio_ibge"})) <> 92 or Table.RowCount(Invalid) <> 0
              then error Error.Record("M06_REFERENCE_CONTRACT", "Esperados 92 municipios RJ unicos e validos do snapshot aprovado.", [Rows = Table.RowCount(Candidate), Invalid = Table.RowCount(Invalid)])
              else Candidate
in
    Checked;

shared lab_m06_municipios_DataDestination =
let
    Catalog = Lakehouse.Contents([CreateNavigationProperties = false, EnableFolding = false]),
    Workspace = Catalog{[workspaceId = "{{WORKSPACE_ID}}"]}[Data],
    Lake = Workspace{[lakehouseId = "{{LAKEHOUSE_ID}}"]}[Data],
    Destination = Lake{[Id = "lab_m06_municipios", ItemKind = "Table"]}?[Data]?
in
    Destination;
