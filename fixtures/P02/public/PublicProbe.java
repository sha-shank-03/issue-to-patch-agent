package fixture;

/** Authored observations, no expected outcomes. */
public final class PublicProbe {
    private static void out(String id, String field, String kind, String value) {
        System.out.println(id + "\t" + field + "\t" + kind + "\t" + value);
    }
    public static void main(String[] args) {
        { ShopApi api = new ShopApi(); boolean ok = true;
          java.util.List<Integer> ids = java.util.List.of();
          try { ids = api.page(2147483647, 2); } catch (RuntimeException rejected) { ok = false; }
          out("overflow_negative", "accepted", "bool", Boolean.toString(ok));
          out("overflow_negative", "ids", "ints", String.join(",", ids.stream().map(x -> Integer.toString(x)).toList()));
        }
        { ShopApi api = new ShopApi(); boolean ok = true;
          java.util.List<Integer> ids = java.util.List.of();
          try { ids = api.page(0, 3); } catch (RuntimeException rejected) { ok = false; }
          out("first", "accepted", "bool", Boolean.toString(ok));
          out("first", "ids", "ints", String.join(",", ids.stream().map(x -> Integer.toString(x)).toList()));
        }
        { ShopApi api = new ShopApi(); boolean ok = true;
          java.util.List<Integer> ids = java.util.List.of();
          try { ids = api.page(0, 0); } catch (RuntimeException rejected) { ok = false; }
          out("bad_size", "accepted", "bool", Boolean.toString(ok));
          out("bad_size", "ids", "ints", String.join(",", ids.stream().map(x -> Integer.toString(x)).toList()));
        }
    }
}
