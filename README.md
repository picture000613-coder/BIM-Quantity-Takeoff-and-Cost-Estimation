# BIM Quantity Takeoff and Cost Estimation

GitHub Pages용 IFC·SketchUp·Rhino·CAD 물량산출 브라우저 뷰어입니다.

## 현재 기능

- 브라우저에서 IFC 파일 열기
- 브라우저에서 SketchUp `.skp` 파일 직접 열기
- 브라우저에서 Rhino `.3dm` 파일 직접 열기
- ASCII DXF의 색상별 선을 분석해 폐합 면적과 높이 기반 예상 체적 산출
- 3D 모델 회전·확대·축소
- 멀리 떨어진 불필요한 객체를 제외하고 메시가 밀집된 건물 영역으로 초기 카메라 자동 집중
- 화면 이동 후 다시 돌아갈 수 있는 `건물 집중 보기` 버튼
- 층·이름·재료·IFC 형식으로 묶인 3D 레이어 목록
- SketchUp Tag별 객체 수, 닫힌 형상 수, 열린 형상 수, 체적·면적 합계
- 닫힌 형상은 체적(m³), 열린 형상은 삼각형 면적(m²)으로 분리 산출
- 레이어별 표시·숨김과 전체 표시·전체 숨김
- IFC 재료별, SketchUp Tag별 또는 Rhino 레이어별 체적·단가·비용 화면
- 콘크리트·유리·금속·목재·벽돌 등 재료군별 일괄단가 적용
- 전체 불러오기 상태 초기화
- Web-IFC JS/WASM을 저장소에 포함해 CDN WASM 404 방지

## CAD 평면 분석

`CAD` 버튼에서 ASCII `.dxf` 파일을 선택한 뒤 도면 단위, 끝점 허용오차, 산정 높이를 지정합니다. 기본값은 `mm`, `1 mm`, `3000 mm`입니다.

- DXF의 `LINE`, `LWPOLYLINE`, `POLYLINE`, `ARC`, `CIRCLE`을 지원합니다.
- 객체 색상 또는 레이어 색상 기준으로 선을 묶습니다. 노란색은 `노랑 (ACI 2)`처럼 표시됩니다.
- 떨어진 끝점이 허용오차 이내이면 같은 점으로 스냅하고 폐합 영역으로 판정합니다.
- 폐합 면적(m²)과 `면적 × 입력 높이` 예상 체적(m³)을 색상별로 표시합니다.
- 분석 후에도 요약 영역에서 끝점 허용오차와 높이를 바꿀 수 있으며, 파일을 다시 선택하지 않고 자동 재계산합니다.
- 미폐합 선은 상태에 개수를 표시하고 체적 계산에서 제외합니다.
- `.dwg`는 로컬 `bim_local_server.py`로 실행하면 설치된 AutoCAD Core Console을 통해 임시 ASCII DXF로 자동 변환한 뒤 분석합니다. 변환 파일은 요청 종료 후 삭제됩니다.
- 정적 GitHub Pages에서는 PC의 AutoCAD를 실행할 수 없으므로 `.dxf`를 사용해야 합니다.

## SketchUp 분석

SketchUp 파일은 브라우저에서 [OpenSKP 1.3.0](https://github.com/iamahsanmehmood/openskp)으로 분석합니다. 파일 자체는 별도 서버로 업로드하지 않습니다.

- 그룹·컴포넌트 경로별로 여러 재질의 메시를 다시 합친 뒤 폐합 여부를 검사합니다.
- 모든 삼각형 모서리가 정확히 두 번 사용된 객체를 닫힌 형상으로 판정합니다.
- 닫힌 형상은 부호 있는 사면체 체적을 합산해 m³로 표시합니다.
- 열린 형상은 체적 대신 실제 삼각형 면적 합계를 m²로 산출하며 별도 면적 단가를 적용할 수 있습니다.
- 닫힌 형상 체적과 열린 형상 면적은 단위가 다르므로 각각 별도의 견적 행으로 표시합니다.
- 오래된 일부 SKP 버전이나 손상된 파일은 OpenSKP가 읽지 못할 수 있습니다. 큰 모델은 브라우저 메모리 한도의 영향을 받습니다.

## Rhino 분석

Rhino 파일은 브라우저에서 Three.js `Rhino3dmLoader`와 McNeel `rhino3dm` WASM으로 읽습니다. 파일 자체는 별도 서버로 업로드하지 않습니다.

- Rhino 레이어별로 Brep·Extrusion·Mesh의 렌더 메시를 모아 객체 단위로 분석합니다.
- 모든 삼각형 모서리가 두 번 사용된 객체는 닫힌 형상, 나머지는 열린 형상으로 판정합니다.
- 닫힌 형상은 m³, 열린 형상은 m²로 분리하며 3DM 문서 단위를 자동으로 미터 기준으로 환산합니다.
- 3DM에 렌더 메시가 저장되지 않은 Brep·Extrusion은 브라우저에서 분석할 형상이 없을 수 있습니다. Rhino에서 음영 또는 렌더링 표시 후 파일을 다시 저장하세요.

## GitHub Pages

`main` 브랜치에 push하면 Pages workflow가 정적 뷰어를 배포합니다. 저장소 Settings → Pages에서 GitHub Actions 배포를 선택하세요.

## 재료 산출 API

GitHub Pages는 정적 호스팅이므로 IfcOpenShell을 실행할 수 없습니다. 공개 페이지에서 IFC 재료 체적을 자동 산출하려면 별도의 HTTPS API 서버가 필요합니다.

- API는 `POST /api/material-takeoff` 경로에서 IFC 바이너리를 받고 JSON 결과를 반환해야 합니다.
- 업로드는 임시 파일로 스트리밍되며 기본 최대 크기는 100MB입니다. QTO가 없는 벽은 제한된 범위에서 형상 체적으로 보완합니다.
- `bim_local_server.py`는 로컬 검증용 API이며 CORS 헤더가 포함되어 있습니다. 공개 배포 시에는 이 서버를 HTTPS가 되는 Python 호스팅에 배포하세요.
- 공개 뷰어에는 기본 API 주소 `https://bim-material-api.onrender.com`이 내부 설정으로 연결되어 있습니다. 사용자 화면에는 API 설정을 노출하지 않습니다. 무료 Render 서비스가 잠든 경우 첫 요청에 시간이 걸릴 수 있습니다.

서버 설정은 환경 변수 `MAX_UPLOAD_MB`(기본 100), `MAX_GEOMETRY_ELEMENTS`(기본 400), `ALLOW_GEOMETRY`로 조정할 수 있습니다.

### Render 배포

저장소의 `render.yaml`을 사용하면 Render에서 `bim-material-api` Web Service를 만들 수 있습니다. Render 대시보드에서 **New > Blueprint**를 선택하고 이 GitHub 저장소를 연결하면 됩니다. 배포가 끝나면 `https://<서비스명>.onrender.com`을 뷰어의 API 주소 입력란에 저장합니다. `/health`가 `{"status":"ok"}`를 반환하면 연결이 준비된 것입니다.
