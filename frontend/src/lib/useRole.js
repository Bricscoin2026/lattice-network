import { useEffect, useState } from "react";
import { api } from "./api";

const DEFAULT_PERMS = {
  can_register_lns: true,
  can_revoke_lns: true,
  can_send_certify: true,
  can_send_pulse: true,
  can_read_plaintext: true,
  can_read_lns_directory: true,
  can_verify_signatures: true,
};

export function useRole() {
  const [me, setMe] = useState({ role: "sovereign", label: "Sovereign Admin", permissions: DEFAULT_PERMS });
  useEffect(() => {
    api.get("/me").then((r) => setMe(r.data)).catch(() => {});
  }, []);
  return me;
}
