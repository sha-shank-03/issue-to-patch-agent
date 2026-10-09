package fixture;

/** Authored observations, no expected outcomes. */
public final class PublicProbe {
    private static void out(String id, String field, String kind, String value) {
        System.out.println(id + "\t" + field + "\t" + kind + "\t" + value);
    }
    public static void main(String[] args) {
        { ShopApi api = new ShopApi(); boolean ok = true;
          try { api.createOrder(null); } catch (RuntimeException rejected) { ok = false; }
          out("null", "accepted", "bool", Boolean.toString(ok));
          out("null", "stock", "int", Long.toString(api.stock()));
          out("null", "orders", "int", Long.toString(api.orders()));
        }
        { ShopApi api = new ShopApi(); boolean ok = true;
          try { api.createOrder(""); } catch (RuntimeException rejected) { ok = false; }
          out("empty", "accepted", "bool", Boolean.toString(ok));
          out("empty", "stock", "int", Long.toString(api.stock()));
          out("empty", "orders", "int", Long.toString(api.orders()));
        }
        { ShopApi api = new ShopApi(); boolean ok = true;
          try { api.createOrder(" "); } catch (RuntimeException rejected) { ok = false; }
          out("space", "accepted", "bool", Boolean.toString(ok));
          out("space", "stock", "int", Long.toString(api.stock()));
          out("space", "orders", "int", Long.toString(api.orders()));
        }
        { ShopApi api = new ShopApi(); boolean ok = true;
          try { api.createOrder("alice"); } catch (RuntimeException rejected) { ok = false; }
          out("name", "accepted", "bool", Boolean.toString(ok));
          out("name", "stock", "int", Long.toString(api.stock()));
          out("name", "orders", "int", Long.toString(api.orders()));
        }
    }
}
