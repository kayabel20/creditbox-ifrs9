"""IFRS 9 Services"""
# Note: DB-dependent services use relative imports that only work
# when running as a proper package (e.g., via FastAPI app).
# The standalone dataframe_ecl_engine works without DB dependencies.
try:
    from .staging_service import StagingService
    from .pd_service import PDService
    from .lgd_service import LGDService
    from .ead_service import EADService
    from .ecl_service import ECLService
    from .reporting_service import ReportingService

    __all__ = [
        "StagingService",
        "PDService",
        "LGDService",
        "EADService",
        "ECLService",
        "ReportingService",
    ]
except (ImportError, ValueError):
    # Running outside package context (e.g., Streamlit with sys.path)
    __all__ = []
