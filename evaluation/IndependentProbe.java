package fixture;

/** Protected authored probe: observations only; Python supplies the oracle. */
public final class IndependentProbe {
    public static void main(String[] args) {
        for (int quantity : new int[] {-1, 0, 1, 5, 99, 100, 101}) {
            ShopApi api = new ShopApi();
            boolean accepted = true;
            try { api.createOrder(quantity); }
            catch (IllegalArgumentException rejected) { accepted = false; }
            System.out.println(quantity + "\t" + accepted + "\t" + api.stock() + "\t" + api.orders());
        }
    }
}
