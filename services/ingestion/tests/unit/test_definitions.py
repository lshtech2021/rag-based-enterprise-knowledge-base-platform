from kb_ingestion.presentation.definitions import defs, edgar_ingestion_job


def test_dagster_definitions_expose_ingestion_job() -> None:
    assert edgar_ingestion_job.name == "edgar_ingestion_job"
    assert defs.get_job_def("edgar_ingestion_job") is not None
