/**
 * data-testid catalog for Lattice Network Admin Console.
 */
export const TID = {
  // Shell
  appShell: "app-shell",
  langToggleIt: "lang-toggle-it",
  langToggleEn: "lang-toggle-en",
  navDashboard: "nav-dashboard",
  navLedger: "nav-ledger",
  navQbft: "nav-qbft",
  navLns: "nav-lns",
  navCertify: "nav-certify",
  navLogs: "nav-logs",
  navPulse: "nav-pulse",
  navVendor: "nav-vendor",
  liveStatus: "live-status",

  // Dashboard
  kpiBlockHeight: "kpi-block-height",
  kpiTransactions: "kpi-total-tx",
  kpiNodes: "kpi-active-nodes",
  kpiCertify: "kpi-certify-total",
  panelLedger: "panel-ledger",
  panelQbft: "panel-qbft",
  panelLns: "panel-lns",
  panelCertify: "panel-certify",
  panelLogs: "panel-logs",

  // Ledger
  ledgerBlocksTable: "ledger-blocks-table",
  txTable: "tx-table",
  txFilterAll: "tx-filter-all",
  txFilterNotary: "tx-filter-notary",
  txFilterRegister: "tx-filter-register",
  txFilterRevoke: "tx-filter-revoke",
  txExportCsv: "tx-export-csv-button",
  txExportJson: "tx-export-json-button",

  // QBFT
  qbftTable: "qbft-table",

  // LNS
  lnsSearchInput: "lns-search-input",
  lnsFilterAll: "lns-filter-all",
  lnsFilterActive: "lns-filter-active",
  lnsFilterRevoked: "lns-filter-revoked",
  lnsTable: "lns-table",
  lnsRowBtn: (name) => `lns-row-${name}`,
  lnsPassportDialog: "lns-passport-dialog",
  lnsPassportClose: "lns-passport-close",
  lnsRevokeBtn: (name) => `lns-revoke-btn-${name}`,
  lnsRevokeDialog: "lns-revoke-dialog",
  lnsRevokeReason: "lns-revoke-reason-input",
  lnsRevokeConfirm: "lns-revoke-confirm-button",
  lnsRevokeCancel: "lns-revoke-cancel-button",
  lnsRegisterOpenBtn: "lns-register-open-button",
  lnsRegisterDialog: "lns-register-dialog",
  lnsRegisterNameInput: "lns-register-name-input",
  lnsRegisterDeptSelect: "lns-register-dept-select",
  lnsRegisterConfirm: "lns-register-confirm-button",
  lnsRegisterCancel: "lns-register-cancel-button",

  // Certify
  certifyMailsTable: "certify-mails-table",
  certifyTabMailbox: "certify-tab-mailbox",
  certifyTabCompose: "certify-tab-compose",
  certifyComposeFrom: "certify-compose-from",
  certifyComposeTo: "certify-compose-to",
  certifyComposeCc: "certify-compose-cc",
  certifyComposeSubject: "certify-compose-subject",
  certifyComposeBody: "certify-compose-body",
  certifyComposeClass: "certify-compose-class",
  certifyComposeSend: "certify-compose-send",
  certifyReceipt: "certify-compose-receipt",

  // Pulse
  pulseSenderSelect: "pulse-sender-select",
  pulseNewChatBtn: "pulse-new-chat-button",
  pulseNewChatDialog: "pulse-new-chat-dialog",
  pulseNewChatRecipient: "pulse-new-chat-recipient",
  pulseNewChatConfirm: "pulse-new-chat-confirm",
  pulseConvList: "pulse-conv-list",
  pulseConvItem: (cid) => `pulse-conv-item-${cid}`,
  pulseMessages: "pulse-messages",
  pulseInput: "pulse-input",
  pulseSendBtn: "pulse-send-button",
  pulseBroadcastBtn: "pulse-broadcast-button",
  pulseBroadcastDialog: "pulse-broadcast-dialog",
  pulseBroadcastInput: "pulse-broadcast-input",
  pulseBroadcastBody: "pulse-broadcast-body",
  pulseBroadcastSend: "pulse-broadcast-send",

  // Vendor
  vendorKpiTenants: "vendor-kpi-tenants",
  vendorKpiNodes: "vendor-kpi-nodes",
  vendorKpiSeats: "vendor-kpi-seats",
  vendorKpiMrr: "vendor-kpi-mrr",
  vendorTenantsTable: "vendor-tenants-table",
  vendorTenantRow: (id) => `vendor-tenant-row-${id}`,
  vendorResidencyBanner: "vendor-residency-banner",

  // Logs
  logsTerminal: "logs-terminal",
  logsPauseBtn: "logs-pause-button",
  logsResumeBtn: "logs-resume-button",
  logsLevelFilter: "logs-level-filter",
  logsSseStatus: "logs-sse-status",
};
