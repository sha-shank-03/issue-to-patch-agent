package fixture;

/** Authored fictional semantic-defect fixture. */
public final class ShopApi {
    private final java.util.List<Integer> ids = java.util.List.of(1, 2, 3, 4, 5, 6);
    public java.util.List<Integer> page(int page, int size) {
        if (page < 0 || size < 1 || size > 100) throw new IllegalArgumentException("invalid page");
        long offset = (long) page * size;
        if (offset >= ids.size()) return java.util.List.of();
        int from = (int) offset;
        int to = Math.min(from + size - 1, ids.size());
        return java.util.List.copyOf(ids.subList(from, to));
    }
}
