package fixture;

/** Authored immutable public reproducer and a small regression check. */
public final class PublicProbe {
    public static void main(String[] args) {
        for (int quantity : new int[] {0, -1, 5}) {
            ShopApi api = new ShopApi();
            boolean accepted = true;
            try { api.createOrder(quantity); }
            catch (IllegalArgumentException rejected) { accepted = false; }
            System.out.println(quantity + "\t" + accepted + "\t" + api.stock() + "\t" + api.orders());
        }
    }
}
