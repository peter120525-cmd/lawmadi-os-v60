"""
Lawmadi OS ADK — Agent Engine 배포 스크립트.

사용법:
  1. 로컬 테스트: adk web lawmadi-adk
  2. Agent Engine 배포: python lawmadi-adk/deploy.py

필수 환경변수:
  - GOOGLE_CLOUD_PROJECT: GCP 프로젝트 ID
  - GOOGLE_CLOUD_LOCATION: 리전 (기본: asia-northeast3)
  - STAGING_BUCKET: GCS 스테이징 버킷 (gs://...)
  - LAWGO_DRF_OC: 국가법령정보센터 API 키
"""

import os
import sys


def deploy():
    """Agent Engine에 Lawmadi OS 에이전트 배포."""
    import vertexai
    from vertexai import agent_engines
    from agent import root_agent

    project = os.environ.get("GOOGLE_CLOUD_PROJECT", "lawmadi-v50")
    location = os.environ.get("GOOGLE_CLOUD_LOCATION", "asia-northeast3")
    staging_bucket = os.environ.get("STAGING_BUCKET", "gs://lawmadi-adk-staging")

    print(f"📦 Lawmadi OS ADK 배포 시작...")
    print(f"   프로젝트: {project}")
    print(f"   리전: {location}")
    print(f"   스테이징: {staging_bucket}")

    # Vertex AI 클라이언트 초기화
    client = vertexai.Client(project=project, location=location)

    # AdkApp 래핑
    app = agent_engines.AdkApp(agent=root_agent)

    # Agent Engine 배포
    print("🚀 Agent Engine 배포 중...")
    remote_agent = client.agent_engines.create(
        agent=app,
        config={
            "display_name": "Lawmadi OS v60",
            "description": "대한민국 법률 의사결정 지원 시스템",
            "requirements": [
                "google-cloud-aiplatform[agent_engines,adk]>=1.112",
                "requests>=2.31.0",
            ],
            "staging_bucket": staging_bucket,
            "env_vars": {
                "LAWGO_DRF_OC": os.environ.get("LAWGO_DRF_OC", ""),
            },
        },
    )

    resource_name = remote_agent.resource_name
    print(f"✅ 배포 완료!")
    print(f"   리소스: {resource_name}")
    print(f"   쿼리 URL: https://{location}-aiplatform.googleapis.com/v1/{resource_name}:query")

    return remote_agent


def test_deployed(resource_name: str = None):
    """배포된 에이전트 테스트."""
    import vertexai

    project = os.environ.get("GOOGLE_CLOUD_PROJECT", "lawmadi-v50")
    location = os.environ.get("GOOGLE_CLOUD_LOCATION", "asia-northeast3")

    client = vertexai.Client(project=project, location=location)

    if resource_name:
        remote_agent = client.agent_engines.get(resource_name)
    else:
        # 가장 최근 배포된 에이전트 조회
        agents = list(client.agent_engines.list())
        if not agents:
            print("❌ 배포된 에이전트가 없습니다.")
            return
        remote_agent = agents[-1]
        print(f"🔍 최근 에이전트: {remote_agent.resource_name}")

    # 테스트 쿼리
    test_queries = [
        "집주인이 보증금을 안 돌려줘요",
        "회사에서 갑자기 잘렸어요",
        "교통사고 났는데 어떻게 해요",
    ]

    import asyncio

    async def run_tests():
        for query in test_queries:
            print(f"\n📝 질문: {query}")
            print("-" * 50)
            async for event in remote_agent.async_stream_query(
                user_id="test-user",
                message=query,
            ):
                if hasattr(event, "content") and event.content:
                    for part in event.content.parts:
                        if hasattr(part, "text"):
                            print(part.text, end="")
            print("\n")

    asyncio.run(run_tests())


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        resource = sys.argv[2] if len(sys.argv) > 2 else None
        test_deployed(resource)
    else:
        deploy()
