begin
wwv_flow_imp_shared.create_security_scheme(
 p_id=>wwv_flow_imp.id(20)
,p_name=>'APP_USERS'
,p_scheme_type=>'NATIVE_FUNCTION_BODY'
,p_attribute_01=>'return synth_pkg.has_any_role;'
,p_error_message=>'Akses ditolak: &APP_USER.'
);
wwv_flow_imp_shared.create_security_scheme(
 p_id=>wwv_flow_imp.id(21)
,p_name=>'ADMIN_RIGHTS'
,p_scheme_type=>'NATIVE_FUNCTION_BODY'
,p_error_message=>'Admin only.'
);
wwv_flow_imp_shared.create_authentication(
 p_id=>wwv_flow_imp.id(10)
,p_name=>'Oracle APEX Accounts'
,p_scheme_type=>'NATIVE_APEX_ACCOUNTS'
);
end;
/
