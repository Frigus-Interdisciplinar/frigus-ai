class Response:
    @staticmethod
    def ok(**kwargs) -> dict:
        return {
            "status": "ok",
            **kwargs
        }

    @staticmethod
    def error(message: Exception | str) -> dict:
        return {
            "status": "error",
            "message": str(message)
        }

__all__ = ["Response"]
