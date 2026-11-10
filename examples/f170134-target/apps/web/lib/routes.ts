export { all, first, qs, safeReturn, type SearchParams } from '@apex2next/runtime-web/routes';

/** Target route of each APEX page (normal pages; modal pages are routed dialogs below their parent). */
export const PAGE_ROUTES: Record<number, string> = {
  100: '/', 190: '/approvals', 200: '/departments', 210: '/items', 300: '/requests', 302: '/requests/detail',
  310: '/request-lines', 400: '/reports/requests', 500: '/admin/users', 510: '/admin/document-types', 9999: '/login',
};
