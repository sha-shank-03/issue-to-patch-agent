package fixture;

/** Authored observations, no expected outcomes. */
public final class PublicProbe {
    private static void out(String id, String field, String kind, String value) {
        System.out.println(id + "\t" + field + "\t" + kind + "\t" + value);
    }
    public static void main(String[] args) {
        { ShopApi api = new ShopApi(); boolean ok = true;
          try { api.createOrder(new int[] {3,3}); } catch (RuntimeException rejected) { ok = false; }
          out("too_many", "accepted", "bool", Boolean.toString(ok));
          out("too_many", "stockA", "int", Long.toString(api.stockA()));
          out("too_many", "stockB", "int", Long.toString(api.stockB()));
          out("too_many", "orders", "int", Long.toString(api.orders()));
          out("too_many", "audit", "int", Long.toString(api.audit()));
        }
        { ShopApi api = new ShopApi(); boolean ok = true;
          try { api.createOrder(new int[] {1}); } catch (RuntimeException rejected) { ok = false; }
          out("single", "accepted", "bool", Boolean.toString(ok));
          out("single", "stockA", "int", Long.toString(api.stockA()));
          out("single", "stockB", "int", Long.toString(api.stockB()));
          out("single", "orders", "int", Long.toString(api.orders()));
          out("single", "audit", "int", Long.toString(api.audit()));
        }
        { ShopApi api = new ShopApi(); boolean ok = true;
          try { api.createOrder(new int[] {0}); } catch (RuntimeException rejected) { ok = false; }
          out("invalid", "accepted", "bool", Boolean.toString(ok));
          out("invalid", "stockA", "int", Long.toString(api.stockA()));
          out("invalid", "stockB", "int", Long.toString(api.stockB()));
          out("invalid", "orders", "int", Long.toString(api.orders()));
          out("invalid", "audit", "int", Long.toString(api.audit()));
        }
    }
}
