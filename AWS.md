# AWS 데모 서버 배포

새 AWS 계정을 만든 뒤 이 저장소에서 배포합니다. **현재는 준비 파일만 있으며 실제 AWS 리소스는 생성하지 않았습니다.**

## 준비된 구성

- 북미 버지니아 리전(`us-east-1`)의 Ubuntu 24.04 / `t3.micro` EC2 한 대. 다른 리전은 `--region`으로 지정합니다.
- Caddy가 HTTPS 인증서 발급·갱신과 WebSocket 프록시를 처리합니다.
- Python 백엔드는 `127.0.0.1:8766`에서 실행합니다. 인터넷에는 80(인증서/HTTPS 리디렉션), 443만 열며 SSH 포트는 열지 않습니다.
- 서버 관리는 AWS Systems Manager(SSM)를 사용합니다. SSH 키 파일을 만들 필요가 없습니다.
- 사용량·치지직 토큰은 암호화된 EBS 디스크의 `/var/lib/stream-chat`에 보관합니다. 서버 재부팅·코드 재배포 때 유지합니다. 인스턴스를 새로 만드는 경우에는 기존 디스크의 데이터를 별도로 복원해야 합니다.
- AI·치지직 키는 SSM Parameter Store의 `SecureString`으로 전달하고, 서버에서는 `root:stream-chat`, 권한 `640`인 `/etc/stream-chat/runtime.json`에 둡니다. 소스 압축파일·데스크톱에는 포함하지 않습니다.
- 한 프로세스가 저장 파일과 OAuth 대기를 관리합니다. 오토스케일링·다중 서버 배포는 지원하지 않습니다.

EC2·EBS·공인 IPv4·S3 사용은 무료 크레딧을 소비할 수 있습니다. 신규 계정의 Free plan/크레딧 잔액과 종료일을 AWS 콘솔에서 확인하세요. 이 구성은 영구 무료를 보장하지 않습니다. OpenAI 요금은 별도입니다. [EC2 무료 사용 조건](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-free-tier-usage.html), [AWS Free Tier](https://aws.amazon.com/free/free-tier-faqs/).

## 계정 생성 후 필요한 것

1. **새 AWS 계정의 12자리 계정 ID**와 해당 계정에 로그인한 AWS CLI v2 프로필.
2. **DNS를 수정할 수 있는 도메인/서브도메인**. 예: `chat.your-domain.com`. 서버 생성 후 표시되는 공인 IP를 DNS A 레코드로 연결합니다. 도메인 구입은 스크립트가 수행하지 않습니다.
3. 현재 운영자 설정 파일 `backend/.env`. `OPENAI_API_KEY`, `CHAT_SERVICE_TOKEN`, `CHZZK_CLIENT_ID`, `CHZZK_CLIENT_SECRET`, `CHZZK_CHANNEL_ID`가 필요합니다. 파일을 대화창이나 GitHub에 올리지 않습니다.

AWS CLI는 [공식 설치 안내](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)를 따릅니다. 최신 CLI의 `aws login`은 루트·IAM·페더레이션 콘솔 로그인을 지원하며 임시 자격 증명을 사용합니다. 필요한 배포 권한이 있어야 합니다. 기존 SSO 프로필이 있으면 `aws sso login --profile stream-chat`도 사용할 수 있습니다. [AWS CLI 로그인](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-sign-in.html).

```powershell
aws login --profile stream-chat
aws sts get-caller-identity --profile stream-chat
```

배포 프로필에는 CloudFormation, EC2/VPC, S3, IAM 역할·인스턴스 프로필 생성 및 `iam:PassRole`, SSM Parameter/Run Command 권한이 필요합니다. 런타임 EC2 역할은 배포 도구가 생성하며 특정 소스 버킷과 자기 설정 파라미터에만 접근합니다. 사용 중인 계정이 입력한 ID와 다르면 스크립트가 리소스 변경 전에 중단합니다.

## 로컬 패키지 만들기 — AWS 호출 없음

`prepare_aws.cmd`를 더블클릭하거나 다음을 실행합니다.

```powershell
.\.venv\Scripts\python.exe -B -m deploy.aws.deploy package
```

결과는 `dist/aws/`에 있습니다.

- `stream-chat-backend.tar.gz`: 백엔드와 서버 실행 파일만 포함.
- `cloudformation.json`: 생성할 AWS 리소스 설정. 비밀 값 없음.
- `manifest.json`: 파일 목록과 압축파일 SHA-256.

기존 `.env`, OAuth 토큰, 캡처 이미지, 실행 기록, 데스크톱 설치본, Git 데이터는 패키지에 들어가지 않습니다. `dist/`와 `build/`도 Git에서 제외됩니다.

## 실제 배포 — AWS 리소스 생성 및 크레딧 사용

아래 계정 ID·도메인은 실제 값으로 바꿉니다. 최초 실행은 VPC, EC2, 공인 IP, 비공개 S3 버킷, IAM 역할을 만들며 다음 실행부터는 같은 서버의 코드만 교체합니다.

```powershell
.\.venv\Scripts\python.exe -B -m deploy.aws.deploy deploy `
  --profile stream-chat `
  --account-id 123456789012 `
  --domain chat.your-domain.com
```

현재 `backend/.env`는 수정하지 않습니다. 서버용 공개 주소·콜백·저장 경로는 배포 과정에서 설정합니다. 기존 `CHAT_SERVICE_TOKEN`을 사용하므로 데스크톱에는 같은 서비스 토큰을 입력하면 됩니다. 여러 계정 설정을 쓰면 `CHZZK_SERVICE_ACCOUNT`에 해당하는 계정 토큰을 사용합니다.

스크립트가 출력하는 `DNS A record`에 따라 DNS를 연결합니다. 처음에는 인증서 발급 전이라 HTTPS 검사에서 종료 코드 2가 나올 수 있습니다. DNS 반영 후 다음 명령으로 다시 확인합니다. 이 검사는 실제 AI 호출이나 방송 채팅 전송을 하지 않습니다.

```powershell
.\.venv\Scripts\python.exe -B -m deploy.aws.deploy check `
  --profile stream-chat `
  --account-id 123456789012
```

검사는 신뢰할 수 있는 HTTPS 인증서와 인증된 `/api/usage` 응답을 모두 확인합니다. 인증 토큰을 포함한 요청은 리디렉션을 따라가지 않습니다. `HTTPS and authenticated service verified`가 나와야 공개 연결 검증이 완료된 것입니다.

## 치지직과 데스크톱 연결

1. 치지직 개발자 센터의 로그인 리디렉션 URL에 `https://chat.your-domain.com/oauth/chzzk/callback`을 등록합니다.
2. 설치 앱의 서비스 연결 주소를 `https://chat.your-domain.com`으로 변경합니다. 소스 앱은 `apps/desktop/.env`의 `CHAT_SERVICE_URL`을 변경하고 다시 실행합니다. API 키는 앱에 넣지 않습니다.
3. 상대방 방송 URL로 승인 링크를 발급합니다.

```powershell
.\.venv\Scripts\python.exe -X utf8 -B -m backend.chzzk_cli invite `
  --service-url https://chat.your-domain.com `
  --channel-url https://chzzk.naver.com/live/상대방채널ID
```

출력의 `authorization_url`만 상대방에게 전달합니다. 상대방은 자기 PC의 브라우저에서 해당 방송 계정으로 승인하면 되며 앱을 설치할 필요가 없습니다. 10분 안에 사용해야 합니다. 앱의 치지직 연결 상태를 확인한 뒤 전송 모드를 선택합니다. [승인 흐름 상세](CHZZK.md#다른-pc에서-승인받기-배포-후).

## 업데이트·문제 확인·종료

- 코드 업데이트는 같은 `deploy` 명령을 실행합니다. 새 가상환경·설정을 먼저 검증하고 서비스를 재시작합니다. 재시작 중 실시간 세션과 진행 중 승인 링크는 끊길 수 있으므로 방송 테스트가 끝난 뒤 배포합니다.
- 설치 또는 내부 상태 검사 실패 시 직전 코드·서버 설정으로 복구를 시도합니다. 실제 EC2에서의 복구 검증은 최초 배포 때 진행해야 합니다. 공개 DNS/인증서 문제는 코드 복구 대신 `check`로 재확인합니다.
- SSM → Run Command에서 출력된 명령 ID로 설치 결과를 확인합니다. Session Manager에서 `sudo systemctl status stream-chat caddy`, `sudo journalctl -u stream-chat -n 50`으로 서버를 확인할 수 있습니다. 키 파일 내용을 출력하거나 공유하지 않습니다.
- EBS 데이터 볼륨 역할을 하는 루트 디스크는 인스턴스 종료 후에도 보존하도록 설정했습니다. 스택 삭제 시 소스 S3 버킷도 보존됩니다. 이들과 별도로 만든 SSM 설정 파라미터는 자동 삭제되지 않으므로, 완전 종료할 때는 필요한 데이터를 백업한 뒤 AWS 콘솔에서 잔여 리소스를 확인합니다. EC2를 정지해도 디스크·공인 IP 요금은 발생할 수 있습니다.
- 현재 작업은 로컬 자동 테스트·패키지/문법·Linux 의존성 검증까지입니다. 새 계정의 IAM, CloudFormation 생성, 실제 Linux 부팅, DNS/TLS, 상대방의 실제 치지직 승인은 아직 검증하지 않았습니다.

구성 근거: [Ubuntu AMI](https://ubuntu.com/aws/docs/aws-how-to/instances/build-cloudformation-templates/), [SSM Ubuntu 지원](https://docs.aws.amazon.com/systems-manager/latest/userguide/agent-install-ubuntu.html), [Parameter Store Standard](https://docs.aws.amazon.com/systems-manager/latest/userguide/parameter-store-advanced-parameters.html), [Caddy HTTPS](https://caddyserver.com/docs/automatic-https).
