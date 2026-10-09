package fixture;

/** Authored observations, no expected outcomes. */
public final class IndependentProbe {
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
        { ShopApi api = new ShopApi(); boolean ok = true;
          try { api.createOrder(new int[] {2147483647, 2147483647, 3}); } catch (RuntimeException rejected) { ok = false; }
          out("overflow_positive", "accepted", "bool", Boolean.toString(ok));
          out("overflow_positive", "stock", "int", Long.toString(api.stock()));
          out("overflow_positive", "orders", "int", Long.toString(api.orders()));
        }
        { ShopApi api = new ShopApi(); boolean ok = true;
          try { api.createOrder(new int[] {2147483647, 2147483647, 2}); } catch (RuntimeException rejected) { ok = false; }
          out("overflow_zero", "accepted", "bool", Boolean.toString(ok));
          out("overflow_zero", "stock", "int", Long.toString(api.stock()));
          out("overflow_zero", "orders", "int", Long.toString(api.orders()));
        }
        { ShopApi api = new ShopApi(); boolean ok = true;
          try { api.createOrder(new int[] {2147483647}); } catch (RuntimeException rejected) { ok = false; }
          out("maximum", "accepted", "bool", Boolean.toString(ok));
          out("maximum", "stock", "int", Long.toString(api.stock()));
          out("maximum", "orders", "int", Long.toString(api.orders()));
        }
        { ShopApi api = new ShopApi(); boolean ok = true;
          try { api.createOrder(new int[] {-1}); } catch (RuntimeException rejected) { ok = false; }
          out("negative", "accepted", "bool", Boolean.toString(ok));
          out("negative", "stock", "int", Long.toString(api.stock()));
          out("negative", "orders", "int", Long.toString(api.orders()));
        }
    }
}
