package fixture;

/** Authored observations, no expected outcomes. */
public final class IndependentProbe {
    private static void out(String id, String field, String kind, String value) {
        System.out.println(id + "\t" + field + "\t" + kind + "\t" + value);
    }
    public static void main(String[] args) {
        { ShopApi api = new ShopApi(); boolean ok = true;
          try { api.createOrder(1, true); } catch (RuntimeException rejected) { ok = false; }
          out("audit_failure", "accepted", "bool", Boolean.toString(ok));
          out("audit_failure", "stockA", "int", Long.toString(api.stockA()));
          out("audit_failure", "stockB", "int", Long.toString(api.stockB()));
          out("audit_failure", "orders", "int", Long.toString(api.orders()));
          out("audit_failure", "audit", "int", Long.toString(api.audit()));
        }
        { ShopApi api = new ShopApi(); boolean ok = true;
          try { api.createOrder(2, false); } catch (RuntimeException rejected) { ok = false; }
          out("success", "accepted", "bool", Boolean.toString(ok));
          out("success", "stockA", "int", Long.toString(api.stockA()));
          out("success", "stockB", "int", Long.toString(api.stockB()));
          out("success", "orders", "int", Long.toString(api.orders()));
          out("success", "audit", "int", Long.toString(api.audit()));
        }
        { ShopApi api = new ShopApi(); boolean ok = true;
          try { api.createOrder(3, true); } catch (RuntimeException rejected) { ok = false; }
          out("larger_failure", "accepted", "bool", Boolean.toString(ok));
          out("larger_failure", "stockA", "int", Long.toString(api.stockA()));
          out("larger_failure", "stockB", "int", Long.toString(api.stockB()));
          out("larger_failure", "orders", "int", Long.toString(api.orders()));
          out("larger_failure", "audit", "int", Long.toString(api.audit()));
        }
        { ShopApi api = new ShopApi(); boolean ok = true;
          try { api.createOrder(0, false); } catch (RuntimeException rejected) { ok = false; }
          out("invalid", "accepted", "bool", Boolean.toString(ok));
          out("invalid", "stockA", "int", Long.toString(api.stockA()));
          out("invalid", "stockB", "int", Long.toString(api.stockB()));
          out("invalid", "orders", "int", Long.toString(api.orders()));
          out("invalid", "audit", "int", Long.toString(api.audit()));
        }
        { ShopApi api = new ShopApi(); boolean ok = true;
          try { api.createOrder(6, false); } catch (RuntimeException rejected) { ok = false; }
          out("oversized", "accepted", "bool", Boolean.toString(ok));
          out("oversized", "stockA", "int", Long.toString(api.stockA()));
          out("oversized", "stockB", "int", Long.toString(api.stockB()));
          out("oversized", "orders", "int", Long.toString(api.orders()));
          out("oversized", "audit", "int", Long.toString(api.audit()));
        }
        { ShopApi api = new ShopApi(); boolean ok = true;
          try { api.createOrder(5, false); } catch (RuntimeException rejected) { ok = false; }
          out("boundary", "accepted", "bool", Boolean.toString(ok));
          out("boundary", "stockA", "int", Long.toString(api.stockA()));
          out("boundary", "stockB", "int", Long.toString(api.stockB()));
          out("boundary", "orders", "int", Long.toString(api.orders()));
          out("boundary", "audit", "int", Long.toString(api.audit()));
        }
        { ShopApi api = new ShopApi(); boolean ok = true;
          try { api.createOrder(-1, true); } catch (RuntimeException rejected) { ok = false; }
          out("invalid_audit", "accepted", "bool", Boolean.toString(ok));
          out("invalid_audit", "stockA", "int", Long.toString(api.stockA()));
          out("invalid_audit", "stockB", "int", Long.toString(api.stockB()));
          out("invalid_audit", "orders", "int", Long.toString(api.orders()));
          out("invalid_audit", "audit", "int", Long.toString(api.audit()));
        }
    }
}
