from __future__ import annotations

from zotero_cli_cc.core.providers.aliyun import AliyunProvider


class ZhipuProvider(AliyunProvider):
    def __init__(
        self,
        api_key: str,
        model: str = "embedding-3-pro",
        base_url: str = "https://open.bigmodel.cn/api/paas/v4",
        batch_size: int = 10,
        max_retries: int = 3,
    ):
        super().__init__(
            api_key=api_key,
            model=model,
            base_url=base_url,
            batch_size=batch_size,
            max_retries=max_retries,
        )

    @property
    def name(self) -> str:
        return "zhipu"
