-- 선택 사항 — MVP 데모에는 필수 아님.
-- "G2는 companies에 읽기 전용"(specs/G2 실행체 경계)을 애플리케이션 코드의 정직함이 아니라
-- DB 권한으로 물리적으로 강제하고 싶을 때만 적용한다.
--
-- 적용하면: G2 백엔드 프로세스는 service_role 키 대신 이 역할로 접속해야
-- companies에 대한 쓰기가 실제로 막힌다. 지금 당장 안 써도 스키마 동작에는 영향 없음.

create role g2_service noinherit nologin;
grant usage on schema public to g2_service;

grant select on companies to g2_service;                      -- 읽기만
grant select, insert, update on segment_sets to g2_service;
grant select, insert, update on segments to g2_service;
grant select, insert, update on segment_assignments to g2_service;
grant select, insert, update on unclassified to g2_service;
-- companies에 대한 insert/update/delete 권한은 의도적으로 부여하지 않는다.
