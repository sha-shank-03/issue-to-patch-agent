package fixture;

/** Authored observations, no expected outcomes. */
public final class PublicProbe {
    private static void out(String id, String field, String kind, String value) {
        System.out.println(id + "\t" + field + "\t" + kind + "\t" + value);
    }
    public static void main(String[] args) {
        { ShopApi api = new ShopApi(); boolean ok = true;
          try { api.createOrder(1, true); } catch (RuntimeException rejected) { ok = false; }
          out("audit_failure", "accepted", "bool", Boolean.toString(ok));
          out("audit_failure", "stockA", "int", Long.toString(api.stockA()));
          out("audit_failure", "stockB", "int", Long.toString(api.stockB()));
        }
        { ShopApi api = new ShopApi(); boolean ok = true;
          try { api.createOrder(2, false); } catch (RuntimeException rejected) { ok = false; }
          out("success", "accepted", "bool", Boolean.toString(ok));
          out("success", "stockA", "int", Long.toString(api.stockA()));
          out("success", "stockB", "int", Long.toString(api.stockB()));
          out("success", "orders", "int", Long.toString(api.orders()));
          out("success", "audit", "int", Long.toString(api.audit()));
        }
    }
}
