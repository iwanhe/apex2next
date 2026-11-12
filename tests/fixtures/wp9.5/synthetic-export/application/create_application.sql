prompt --application/create_application
begin
wwv_flow_imp.component_begin (
 p_version_yyyy_mm_dd=>'2026.04.07'
,p_release=>'26.2.1'
,p_default_application_id=>900
);
wwv_imp_workspace.create_flow(
 p_id=>wwv_flow.g_flow_id
,p_owner=>nvl(wwv_flow_application_install.get_schema,'SYNTH')
,p_name=>nvl(wwv_flow_application_install.get_application_name,'Synthetic App')
,p_alias=>nvl(wwv_flow_application_install.get_application_alias,'SYN')
,p_flow_language=>'en'
,p_date_format=>'DD-MON-YYYY'
,p_authentication_id=>wwv_flow_imp.id(10)
,p_flow_version=>'Release 1.0'
,p_security_scheme=>wwv_flow_imp.id(20)
);
wwv_flow_imp.component_end;
end;
/
