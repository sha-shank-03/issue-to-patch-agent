package fixture;

/** Authored fictional semantic-defect fixture. */
public final class ShopApi {
    private long stock = 3000000000L;
    private int orders = 0;
    public long stock() { return stock; }
    public int orders() { return orders; }
    public void createOrder(int[] quantities) {
        int total = 0;
        for (int q : quantities) {
            if (q <= 0) throw new IllegalArgumentException("positive quantities required");
            total += q;
        }
        if (total > Integer.MAX_VALUE) throw new IllegalArgumentException("total exceeds limit");
        stock -= total; orders++;
    }
}
