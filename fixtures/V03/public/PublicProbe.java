package fixture;

/** Authored observations, no expected outcomes. */
public final class PublicProbe {
    private static void out(String id, String field, String kind, String value) {
        System.out.println(id + "\t" + field + "\t" + kind + "\t" + value);
    }
    public static void main(String[] args) {
        { ShopApi api = new ShopApi(); boolean ok = true;
          try { api.createOrder(new int[] {2147483647, 2147483647}); } catch (RuntimeException rejected) { ok = false; }
          out("overflow_negative", "accepted", "bool", Boolean.toString(ok));
          out("overflow_negative", "stock", "int", Long.toString(api.stock()));
          out("overflow_negative", "orders", "int", Long.toString(api.orders()));
        }
        { ShopApi api = new ShopApi(); boolean ok = true;
          try { api.createOrder(new int[] {1, 2}); } catch (RuntimeException rejected) { ok = false; }
          out("small", "accepted", "bool", Boolean.toString(ok));
          out("small", "stock", "int", Long.toString(api.stock()));
          out("small", "orders", "int", Long.toString(api.orders()));
        }
        { ShopApi api = new ShopApi(); boolean ok = true;
          try { api.createOrder(new int[] {0}); } catch (RuntimeException rejected) { ok = false; }
          out("zero", "accepted", "bool", Boolean.toString(ok));
          out("zero", "stock", "int", Long.toString(api.stock()));
          out("zero", "orders", "int", Long.toString(api.orders()));
        }
    }
}
