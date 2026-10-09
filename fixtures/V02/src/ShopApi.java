package fixture;

/** Authored fictional semantic-defect fixture. */
public final class ShopApi {
    private int stock = 200, orders = 0;
    public int stock() { return stock; }
    public int orders() { return orders; }
    public void createOrder(String customer) {
        if (customer == null || customer.isEmpty()) throw new IllegalArgumentException("customer required");
        stock -= 5; orders++;
    }
}
