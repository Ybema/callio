class BaseAdapter:
    @classmethod
    def get_filter_options(cls) -> list[dict]:
        """
        Return filter schema for this source type.
        Each item:
        {
          key: str,
          label: str,
          type: "multi-select" | "single-select",
          options: [{ value: str, label: str }]
        }
        """
        return []

    async def fetch_calls(
        self,
        max_calls: int = 200,
        browser=None,
        filter_config: dict | None = None,
    ) -> list[dict]:
        raise NotImplementedError
