package fixture;

/** Authored observations, no expected outcomes. */
public final class PublicProbe {
    private static void out(String id, String field, String kind, String value) {
        System.out.println(id + "\t" + field + "\t" + kind + "\t" + value);
    }
    public static void main(String[] args) {
        { ShopApi api = new ShopApi(); boolean ok = true;
          try { api.createOrder(2, 2); } catch (RuntimeException rejected) { ok = false; }
          out("second_failure", "accepted", "bool", Boolean.toString(ok));
          out("second_failure", "stockA", "int", Long.toString(api.stockA()));
          out("second_failure", "stockB", "int", Long.toString(api.stockB()));
          out("second_failure", "orders", "int", Long.toString(api.orders()));
          out("second_failure", "audit", "int", Long.toString(api.audit()));
        }
        { ShopApi api = new ShopApi(); boolean ok = true;
          try { api.createOrder(1, 1); } catch (RuntimeException rejected) { ok = false; }
          out("success", "accepted", "bool", Boolean.toString(ok));
          out("success", "stockA", "int", Long.toString(api.stockA()));
          out("success", "stockB", "int", Long.toString(api.stockB()));
          out("success", "orders", "int", Long.toString(api.orders()));
          out("success", "audit", "int", Long.toString(api.audit()));
        }
        { ShopApi api = new ShopApi(); boolean ok = true;
          try { api.createOrder(0, 1); } catch (RuntimeException rejected) { ok = false; }
          out("invalid", "accepted", "bool", Boolean.toString(ok));
          out("invalid", "stockA", "int", Long.toString(api.stockA()));
          out("invalid", "stockB", "int", Long.toString(api.stockB()));
          out("invalid", "orders", "int", Long.toString(api.orders()));
          out("invalid", "audit", "int", Long.toString(api.audit()));
        }
    }
}
